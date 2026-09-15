"""
Automated, safe backup of the live JointX SQLite database (Tier 1 production
integration: backups/disaster recovery).

Uses sqlite3's own online backup API (Connection.backup()) rather than
copying the .db file directly -- a plain file copy can capture a database
mid-write and produce a corrupted backup; the backup API takes a consistent
snapshot even while the app is running.

Usage (run on a schedule -- see the bottom of this file for how to automate
it on Windows/Linux):
    python tools/backup_db.py

What it does:
  1. Takes a timestamped, consistent snapshot of Config.DATABASE_PATH into
     Config.BACKUP_DIR, gzip-compressed.
  2. Deletes old local backups beyond Config.BACKUP_RETENTION_COUNT.
  3. If Config.BACKUP_S3_BUCKET is set AND boto3 is installed, also uploads
     the new backup off-device. This step is skipped (not faked) if either
     precondition isn't met -- the script prints exactly why.

This never uploads anything unless BACKUP_S3_BUCKET is explicitly configured;
by default backups stay local only, which is still far better than no
backups at all but is NOT truly disaster-proof (a lost/destroyed device
loses local backups too) -- configure off-device storage for real protection.
"""
import gzip
import os
import shutil
import sqlite3
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import Config  # noqa: E402
from backend.utils.logger import get_logger  # noqa: E402

logger = get_logger(__name__)


def backup_database() -> str:
    """Returns the path to the newly created, gzip-compressed backup file."""
    if not os.path.exists(Config.DATABASE_PATH):
        raise FileNotFoundError(f"No database found at {Config.DATABASE_PATH} -- nothing to back up")

    os.makedirs(Config.BACKUP_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    raw_path = os.path.join(Config.BACKUP_DIR, f"jointx_{timestamp}.db")
    gz_path = raw_path + ".gz"

    source = sqlite3.connect(Config.DATABASE_PATH)
    dest = sqlite3.connect(raw_path)
    try:
        source.backup(dest)  # consistent snapshot even if source is mid-write
    finally:
        dest.close()
        source.close()

    with open(raw_path, "rb") as f_in, gzip.open(gz_path, "wb") as f_out:
        shutil.copyfileobj(f_in, f_out)
    os.remove(raw_path)

    logger.info("Database backed up to %s", gz_path)
    return gz_path


def prune_old_backups():
    if not os.path.isdir(Config.BACKUP_DIR):
        return
    backups = sorted(
        (f for f in os.listdir(Config.BACKUP_DIR) if f.startswith("jointx_") and f.endswith(".db.gz")),
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
    s3.upload_file(local_path, Config.BACKUP_S3_BUCKET, key)
    logger.info("Uploaded backup to s3://%s/%s", Config.BACKUP_S3_BUCKET, key)
    print(f"Uploaded to s3://{Config.BACKUP_S3_BUCKET}/{key}")


def main():
    path = backup_database()
    print(f"Backup written: {path}")
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
