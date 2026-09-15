"""
Restores a JointX database from an encrypted backup produced by
tools/backup_db.py (spec: P1 data layer #6 -- "a backup nobody has restored
is not a backup").

Usage:
    python tools/restore_db.py --backup backups/jointx_20260101_020000.db.enc --dry-run
    python tools/restore_db.py --backup backups/jointx_20260101_020000.db.enc --output /var/lib/jointx/jointx.db

--dry-run decrypts and verifies the backup (runs SQLite's own integrity
check against it) WITHOUT writing anything to --output -- always run this
first, and periodically even when you're not in the middle of an actual
incident, to prove the backup pipeline still works.

REHEARSED RESTORE PROCEDURE (run this for real at least once, e.g. quarterly,
against a throwaway path -- not just read about it):
  1. python tools/backup_db.py                     # produce a fresh backup
  2. python tools/restore_db.py --backup <path> --dry-run
     -> confirms decryption succeeds and SQLite integrity_check passes
  3. python tools/restore_db.py --backup <path> --output /tmp/restore_test.db
  4. Open /tmp/restore_test.db with the app (JOINTX_DB_PATH=/tmp/restore_test.db
     python app.py) and confirm patient/screening data actually looks right,
     not just that the file opens.
  5. Delete /tmp/restore_test.db when done -- it's decrypted PHI, don't leave
     it lying around.
Record the date this was last actually performed in your deployment's own
runbook, not just in this file.
"""
import argparse
import gzip
import os
import sqlite3
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.utils import crypto  # noqa: E402


def restore_backup(backup_path: str, output_path: str = None) -> dict:
    """
    Decrypts and decompresses a backup file, verifies it with SQLite's
    integrity_check, and (unless output_path is None, i.e. dry-run) writes
    the restored database to output_path.

    Returns {"integrity_ok": bool, "integrity_message": str, "row_counts": dict}.
    """
    with open(backup_path, "rb") as f:
        encrypted = f.read()

    compressed = crypto.decrypt_bytes(encrypted)
    raw_bytes = gzip.decompress(compressed)

    # Verify via a temporary file -- sqlite3 needs a real file (or :memory:)
    # to open, and we want to run integrity_check before touching the real
    # output path.
    fd, tmp_path = tempfile.mkstemp(suffix=".db")
    try:
        os.close(fd)
        with open(tmp_path, "wb") as f:
            f.write(raw_bytes)

        conn = sqlite3.connect(tmp_path)
        integrity_result = conn.execute("PRAGMA integrity_check").fetchone()[0]
        integrity_ok = integrity_result == "ok"

        row_counts = {}
        if integrity_ok:
            for table in ("patients", "screenings", "healthcare_workers", "predictions"):
                try:
                    row_counts[table] = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                except sqlite3.OperationalError:
                    row_counts[table] = None
        conn.close()

        if output_path and integrity_ok:
            os.makedirs(os.path.dirname(os.path.abspath(output_path)) or ".", exist_ok=True)
            with open(tmp_path, "rb") as src, open(output_path, "wb") as dst:
                dst.write(src.read())

        return {
            "integrity_ok": integrity_ok,
            "integrity_message": integrity_result,
            "row_counts": row_counts,
        }
    finally:
        os.remove(tmp_path)  # never leave a decrypted copy behind, even the verification temp file


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--backup", required=True, help="Path to a .db.enc file from tools/backup_db.py")
    parser.add_argument("--output", help="Where to write the restored database. Omit for --dry-run.")
    parser.add_argument("--dry-run", action="store_true", help="Verify only, write nothing")
    args = parser.parse_args()

    if not args.dry_run and not args.output:
        print("Specify --output PATH, or pass --dry-run to only verify the backup.")
        sys.exit(1)

    output_path = None if args.dry_run else args.output
    result = restore_backup(args.backup, output_path)

    print(f"Integrity check: {result['integrity_message']}")
    if result["integrity_ok"]:
        print("Row counts:")
        for table, count in result["row_counts"].items():
            print(f"  {table}: {count}")
        if output_path:
            print(f"Restored database written to: {output_path}")
        else:
            print("Dry run only -- nothing written. Re-run with --output PATH to actually restore.")
    else:
        print("BACKUP FAILED INTEGRITY CHECK -- do not trust this backup.")
        sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) == 1:
        print(__doc__)
        sys.exit(0)
    main()
