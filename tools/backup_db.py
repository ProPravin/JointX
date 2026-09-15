"""
Automated, safe, ENCRYPTED backup of the live JointX SQLite database
(spec: P1 data layer #6).

Uses sqlite3's own online backup API (Connection.backup()) into an
IN-MEMORY database, then serializes and encrypts that entirely in RAM --
an unencrypted copy of the database NEVER touches disk at any point, not
even transiently. This matters even though PHI columns are already
encrypted at the row level (backend/utils/crypto.py): the backup also
contains password hashes, audit logs, and clinical review data that
deserve the same protection, and a backup file is exactly the kind of
artifact that ends up copied to a USB stick or uploaded somewhere.

Usage (run on a schedule -- see the bottom of this file for how to automate
it on Windows/Linux):
    python tools/backup_db.py

What it does:
  1. Takes a consistent in-memory snapshot of Config.DATABASE_PATH.
  2. Compresses, then encrypts it (JOINTX_DATA_KEY), and writes ONLY the
     encrypted bytes to Config.BACKUP_DIR.
  3. Deletes old local backups beyond Config.BACKUP_RETENTION_COUNT.
  4. If Config.BACKUP_S3_BUCKET is set AND boto3 is installed, also uploads
     the (already-encrypted) backup off-device. Skipped, not faked, if
     either precondition isn't met.

See tools/restore_db.py for the corresponding, REHEARSED restore procedure
-- a backup nobody has restored is not a backup.
"""
import gzip
import os
import sqlite3
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import Config  # noqa: E402
from backend.utils.logger import get_logger  # noqa: E402
from backend.utils import crypto  # noqa: E402

logger = get_logger(__name__)

BACKUP_EXTENSION = ".db.enc"


def _snapshot_bytes() -> bytes:
    """
    Returns a consistent, uncompressed snapshot of the live database as raw
    bytes, using an in-memory destination so nothing unencrypted is ever
    written to disk. Requires Python 3.11+ for Connection.serialize().
    """
    if not os.path.exists(Config.DATABASE_PATH):
        raise FileNotFoundError(f"No database found at {Config.DATABASE_PATH} -- nothing to back up")

    source = sqlite3.connect(Config.DATABASE_PATH)
    dest = sqlite3.connect(":memory:")
    try:
        source.backup(dest)  # consistent snapshot even if source is mid-write (WAL-aware)
        return dest.serialize()
    finally:
        dest.close()
        source.close()


def backup_database() -> str:
    """Returns the path to the newly created, compressed + encrypted backup file."""
    if not crypto.is_configured():
        raise crypto.CryptoNotConfiguredError(
            "JOINTX_DATA_KEY is not set -- refusing to create a backup that would "
            "otherwise have to be written unencrypted. See docs/KEY_MANAGEMENT.md."
        )

    raw_bytes = _snapshot_bytes()
    compressed = gzip.compress(raw_bytes)
    encrypted = crypto.encrypt_bytes(compressed)

    os.makedirs(Config.BACKUP_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = os.path.join(Config.BACKUP_DIR, f"jointx_{timestamp}{BACKUP_EXTENSION}")

    # Write only the final encrypted bytes -- at no point does raw_bytes or
    # compressed touch disk.
    with open(out_path, "wb") as f:
        f.write(encrypted)

    logger.info("Encrypted database backup written to %s", out_path)
    return out_path


def prune_old_backups():
    if not os.path.isdir(Config.BACKUP_DIR):
        return
    backups = sorted(
        (f for f in os.listdir(Config.BACKUP_DIR) if f.startswith("jointx_") and f.endswith(BACKUP_EXTENSION)),
        reverse=True,
    )
    for stale in backups[Config.BACKUP_RETENTION_COUNT:]:
        path = os.path.join(Config.BACKUP_DIR, stale)
        os.remove(path)
        logger.info("Pruned old backup %s (beyond retention count %d)", stale, Config.BACKUP_RETENTION_COUNT)


def upload_to_s3(local_path: str):
    if not Config.BACKUP_S3_BUCKET:
        print("Off-device upload skipped: JOINTX_BACKUP_S3_BUCKET is not configured (local-only backup).")
        return
    try:
        import boto3
    except ImportError:
        print(
            "Off-device upload skipped: JOINTX_BACKUP_S3_BUCKET is set but boto3 is not installed. "
            "Run: pip install boto3"
        )
        return

    key = f"jointx-backups/{os.path.basename(local_path)}"
    s3 = boto3.client("s3")  # uses boto3's standard AWS credential chain
    # local_path is already encrypted -- the upload step never has plaintext to protect.
    s3.upload_file(local_path, Config.BACKUP_S3_BUCKET, key)
    logger.info("Uploaded encrypted backup to s3://%s/%s", Config.BACKUP_S3_BUCKET, key)
    print(f"Uploaded to s3://{Config.BACKUP_S3_BUCKET}/{key}")


def main():
    path = backup_database()
    print(f"Encrypted backup written: {path}")
    prune_old_backups()
    upload_to_s3(path)


if __name__ == "__main__":
    main()

# --- Scheduling this script ---
#
# Windows (Task Scheduler), run daily at 2 AM:
#   schtasks /create /tn "JointX DB Backup" /tr "\"E:\jointx\jointx\.venv\Scripts\python.exe\" \"E:\jointx\jointx\tools\backup_db.py\"" /sc daily /st 02:00
#
# Linux/Raspberry Pi (cron), run daily at 2 AM -- add to `crontab -e`:
#   0 2 * * * /path/to/jointx/.venv/bin/python /path/to/jointx/tools/backup_db.py >> /path/to/jointx/logs/backup.log 2>&1
#
# RETENTION POLICY: JOINTX_BACKUP_RETENTION_COUNT (default 30) keeps that many
# most-recent local backups; older ones are pruned automatically on each run.
# This is a simple count-based policy, not calendar-aware (no separate
# daily/weekly/monthly tiers) -- appropriate for a single-device PHC backup,
# reconsider for the central server (see central_server/) which holds every
# site's data.
