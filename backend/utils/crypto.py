"""
Application-level column encryption for PHI (spec: P1 data layer #4).

WHY APPLICATION-LEVEL, NOT SQLCIPHER: a failed pysqlcipher3 build on a
Raspberry Pi in the field is unrecoverable without a working internet
connection and a compiler toolchain -- exactly the situation this offline-
first tool is meant to survive. A pure-Python column encryptor has no build
step, degrades to a clear ImportError/RuntimeError instead of a silent
failure to even start, and leaves the existing sqlite3 access layer in
database/database.py completely untouched.

This is the ONLY module in the codebase that touches encryption. Every
caller that needs to store or read an encrypted column goes through
encrypt_field()/decrypt_field() here -- never ad-hoc crypto at the call site
(spec requirement).

Key handling:
  - JOINTX_DATA_KEY must be a Fernet key: 32 url-safe base64-encoded bytes.
    Generate one with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
  - Read from the environment only, never from a file inside the repo --
    see docs/KEY_MANAGEMENT.md for where it actually lives on a deployed
    device and how it's injected at boot.
  - There is deliberately no fallback to "store as plaintext if no key is
    configured" -- callers get a loud RuntimeError instead, because a silent
    plaintext fallback is exactly how PHI ends up unencrypted on a device.
"""
import hashlib
import hmac
import os

from cryptography.fernet import Fernet, InvalidToken


class CryptoNotConfiguredError(RuntimeError):
    pass


class DecryptionError(RuntimeError):
    pass


def _get_key() -> bytes:
    key = os.environ.get("JOINTX_DATA_KEY", "")
    if not key:
        raise CryptoNotConfiguredError(
            "JOINTX_DATA_KEY is not set. PHI columns cannot be encrypted or "
            "decrypted without it. Generate one with:\n"
            "    python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\"\n"
            "See docs/KEY_MANAGEMENT.md for how to store and inject it on a deployed device."
        )
    return key.encode() if isinstance(key, str) else key


def _fernet() -> Fernet:
    try:
        return Fernet(_get_key())
    except ValueError as e:
        raise CryptoNotConfiguredError(f"JOINTX_DATA_KEY is not a valid Fernet key: {e}") from e


def encrypt_field(plaintext) -> str:
    """Returns a base64 ciphertext string, or None if plaintext is None/empty (never encrypt an absence into a value)."""
    if plaintext is None or plaintext == "":
        return None
    return _fernet().encrypt(str(plaintext).encode("utf-8")).decode("ascii")


def decrypt_field(ciphertext) -> str:
    """Returns the original plaintext string, or None if ciphertext is None."""
    if ciphertext is None:
        return None
    try:
        return _fernet().decrypt(ciphertext.encode("ascii")).decode("utf-8")
    except InvalidToken as e:
        raise DecryptionError(
            "Could not decrypt a PHI field -- wrong JOINTX_DATA_KEY, or the value "
            "was never encrypted with this key (e.g. a legacy plaintext row that "
            "hasn't been through the encryption backfill migration yet)."
        ) from e


def encrypt_bytes(plaintext: bytes) -> bytes:
    """Raw-bytes counterpart to encrypt_field(), for whole-file payloads (see tools/backup_db.py)."""
    return _fernet().encrypt(plaintext)


def decrypt_bytes(ciphertext: bytes) -> bytes:
    """Raw-bytes counterpart to decrypt_field()."""
    try:
        return _fernet().decrypt(ciphertext)
    except InvalidToken as e:
        raise DecryptionError(
            "Could not decrypt -- wrong JOINTX_DATA_KEY, or this data was encrypted with a different key."
        ) from e


def hash_field(value) -> str:
    """
    Deterministic HMAC-SHA256 hex digest for exact-match lookup/deduplication
    (e.g. phone_hash, full_name_hash) WITHOUT decrypting every row. Normalizes
    the input (strip + casefold) so lookups aren't sensitive to whitespace or
    case, which would otherwise defeat the entire point of a lookup hash.
    Uses the same JOINTX_DATA_KEY as a keyed hash so field values can't be
    matched against a plain rainbow-table style guess of common names/numbers.
    """
    if value is None or value == "":
        return None
    normalized = str(value).strip().casefold().encode("utf-8")
    return hmac.new(_get_key(), normalized, hashlib.sha256).hexdigest()


def is_configured() -> bool:
    return bool(os.environ.get("JOINTX_DATA_KEY"))
