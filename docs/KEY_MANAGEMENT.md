# Key Management

JointX encrypts patient PHI (full name, phone number, village/area) at the
application layer before it ever reaches SQLite (see
`backend/utils/crypto.py`). That encryption is only as good as how the key
behind it — `JOINTX_DATA_KEY` — is generated, stored, injected, and rotated.
This document covers all of that, plus what to do if a device is lost or
stolen.

## What the key actually is

`JOINTX_DATA_KEY` is a [Fernet](https://cryptography.io/en/latest/fernet/)
key: 32 random bytes, base64url-encoded. Generate one with:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

This single key is used for two things, both inside `backend/utils/crypto.py`
only:
- **Encrypting** `patients.full_name`, `patients.contact_phone`,
  `patients.village_or_area` (Fernet, authenticated encryption)
- **Deterministic hashing** (`full_name_hash`, `contact_phone_hash`) via
  HMAC-SHA256 keyed with the same value, so exact-match lookup and
  deduplication work without decrypting every row

It is also reused (deliberately, to avoid managing two secrets) to encrypt
database backups end-to-end — see `tools/backup_db.py`.

## Where the key lives on a deployed device (Raspberry Pi)

**Never inside the repository, never in a file the application code ships
with.** The key is read from the `JOINTX_DATA_KEY` environment variable only
(`os.environ.get`, not a config file `git` ever sees).

Recommended: a root-owned environment file outside the app directory, loaded
by the systemd service unit:

```ini
# /etc/jointx/data-key.env  (mode 600, owned by root)
JOINTX_DATA_KEY=<the generated key>
```

```ini
# /etc/systemd/system/jointx.service
[Service]
EnvironmentFile=/etc/jointx/data-key.env
User=jointx
...
```

This keeps the key out of `/opt/jointx` (the application directory, which
per the three-layer model in `config.py` holds code only, never data or
secrets) and out of anything a `git archive`-built release could ever
contain.

## How it's injected at boot

1. systemd reads `EnvironmentFile=` before starting the `jointx` service
   user's process.
2. `config.py`'s `Config.DATA_KEY` picks it up from the environment at
   import time; `backend/utils/crypto.py` reads `os.environ` directly on
   every call (not cached), so a key rotation only requires a service
   restart, not a code change.
3. `Config.validate_for_production()` refuses to start at all if
   `JOINTX_DATA_KEY` is unset and `JOINTX_DEMO_MODE=false` — a production
   boot can never silently run without encryption configured.

## Rotating the key

Rotating means: generate a new key, re-encrypt every existing encrypted
value with it, then switch the running config over.

```bash
# 1. Generate the new key
NEW_KEY=$(python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")

# 2. Stop the app (no writes during re-encryption)
sudo systemctl stop jointx

# 3. Re-key the database (see migrations/002_encrypt_phi.py once P3's
#    migration framework lands; until then this is a manual, dry-run-first
#    operation -- re-run tools/backup_db.py with the OLD key first as a
#    safety net before touching anything)
python tools/backup_db.py   # safety backup under the OLD key

python -c "
import os
os.environ['JOINTX_DATA_KEY'] = '<OLD_KEY>'
from backend.utils import crypto
from database.database import get_cursor

NEW_KEY = '<NEW_KEY>'

with get_cursor() as cur:
    cur.execute('SELECT id, full_name, contact_phone, village_or_area FROM patients')
    rows = cur.fetchall()

decrypted = [(r['id'], crypto.decrypt_field(r['full_name']),
              crypto.decrypt_field(r['contact_phone']),
              crypto.decrypt_field(r['village_or_area'])) for r in rows]

os.environ['JOINTX_DATA_KEY'] = NEW_KEY
with get_cursor(commit=True) as cur:
    for pid, name, phone, village in decrypted:
        cur.execute(
            'UPDATE patients SET full_name=?, full_name_hash=?, contact_phone=?, '
            'contact_phone_hash=?, village_or_area=? WHERE id=?',
            (crypto.encrypt_field(name), crypto.hash_field(name),
             crypto.encrypt_field(phone), crypto.hash_field(phone),
             crypto.encrypt_field(village), pid),
        )
print('Re-keyed', len(decrypted), 'patient rows.')
"

# 4. Update /etc/jointx/data-key.env with NEW_KEY, destroy the old key value
#    (don't leave it in shell history -- clear it, or run this from a script
#    file you delete afterward)

# 5. Restart
sudo systemctl start jointx

# 6. Verify: log in, open a patient record, confirm it still reads correctly
```

**Old backups encrypted under the old key remain readable only with the old
key.** Either keep the old key archived securely alongside those backups
(clearly labeled with its retirement date), or re-encrypt existing backups
under the new key using the same pattern as above (decrypt with old,
encrypt with new) if you need them to remain restorable going forward.

## Device loss or theft

The SD card is removable by design (it's how a Pi is imaged and re-imaged)
— assume it *will* be removed, lost, or stolen at some point in the field.

1. **`JOINTX_DATA_KEY` lives in `/etc/jointx/data-key.env`, not on the
   removable card's application partition** — if your deployment separates
   the OS/data partition from a removable card, keep the key off the
   removable media entirely. If the whole SD card (OS included) is what's
   at risk, LUKS full-disk encryption (below) is the layer that actually
   protects the key at rest, not this document's guidance alone.
2. Treat the device's key as **compromised the moment the device is
   confirmed lost**. Rotate it (procedure above) using the last known-good
   backup, on a replacement device.
3. Revoke that device's sync credentials on the central server (see
   `central_server/` — per-device credentials, not a shared token, are
   required specifically so one device's compromise doesn't require
   re-keying the whole fleet).
4. Log the incident (date, device ID, facility) in your deployment's own
   incident record — this codebase does not include an incident-tracking
   system, that's a program-management responsibility, not a software one.

## LUKS full-disk encryption — REQUIRED second layer

Application-level column encryption protects the specific PHI columns
against **someone who copies the database file off the card** (e.g. by
mounting it in another machine, or a stolen backup). It does **not**
protect worker credentials' password hashes' salt exposure patterns, audit
log metadata, or anything else on the card if the *entire SD card* is
imaged by someone with physical access.

**LUKS (Linux Unified Key Setup) full-disk encryption of the SD card is a
required second layer, not optional hardening**, for any device that will
hold real patient data in the field:

```bash
# During initial Pi imaging (not on a running production device):
cryptsetup luksFormat /dev/sdX2          # the data partition, not /boot
cryptsetup open /dev/sdX2 jointx_data
mkfs.ext4 /dev/mapper/jointx_data
# mount, install JointX onto it, configure /etc/crypttab for boot-time unlock
```

The LUKS passphrase/keyfile is a **separate secret from `JOINTX_DATA_KEY`**
— losing one does not compromise the other, which is intentional defense in
depth. Document your specific LUKS unlock method (passphrase entry at boot
vs. a keyfile on a separate boot partition vs. network-bound unlocking) in
your deployment's own `FIELD_SETUP.md` once that exists (see the field
deployment pack, planned but not yet written as of this document).

## What crypto.py deliberately does NOT do

- **No plaintext fallback.** If `JOINTX_DATA_KEY` is unset,
  `encrypt_field()`/`decrypt_field()`/`hash_field()` all raise
  `CryptoNotConfiguredError` rather than silently storing plaintext. A
  loud startup failure is the correct behavior here, not a quiet security
  regression.
- **No key stored in the database itself, ever**, even encrypted-with-a-
  master-key. The key lives only in the environment.
- **No SQLCipher.** See the rationale comment at the top of
  `backend/utils/crypto.py` — a failed native-extension build on a Pi in
  the field is a worse failure mode than anything this simpler approach
  costs in cryptographic sophistication.
