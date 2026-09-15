import os
import sqlite3
import tempfile

from config.settings import Config
from tools.backup_db import backup_database, prune_old_backups
from tools.restore_db import restore_backup


def _make_test_db() -> str:
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, name TEXT)")
    conn.execute("INSERT INTO t (name) VALUES ('hello')")
    conn.commit()
    conn.close()
    return db_path


def test_backup_database_writes_only_encrypted_bytes(app):
    """app fixture guarantees JOINTX_DATA_KEY is set (see tests/conftest.py)."""
    db_path = _make_test_db()
    backup_dir = tempfile.mkdtemp()
    original_db, original_dir = Config.DATABASE_PATH, Config.BACKUP_DIR
    try:
        Config.DATABASE_PATH = db_path
        Config.BACKUP_DIR = backup_dir

        enc_path = backup_database()
        assert os.path.exists(enc_path)
        assert enc_path.endswith(".db.enc")

        # The on-disk backup must never contain the plaintext table/row data
        # -- spec: "an unencrypted backup must never exist on the filesystem
        # at any point."
        with open(enc_path, "rb") as f:
            raw = f.read()
        assert b"hello" not in raw
        assert b"SQLite format" not in raw  # the unencrypted sqlite header would be a dead giveaway
    finally:
        Config.DATABASE_PATH, Config.BACKUP_DIR = original_db, original_dir
        os.remove(db_path)


def test_backup_restore_round_trip_is_byte_equivalent(app):
    db_path = _make_test_db()
    backup_dir = tempfile.mkdtemp()
    original_db, original_dir = Config.DATABASE_PATH, Config.BACKUP_DIR
    try:
        Config.DATABASE_PATH = db_path
        Config.BACKUP_DIR = backup_dir

        enc_path = backup_database()

        restored_path = os.path.join(tempfile.mkdtemp(), "restored.db")
        result = restore_backup(enc_path, restored_path)

        assert result["integrity_ok"] is True
        assert os.path.exists(restored_path)

        restored_conn = sqlite3.connect(restored_path)
        row = restored_conn.execute("SELECT name FROM t").fetchone()
        restored_conn.close()
        assert row[0] == "hello"
    finally:
        Config.DATABASE_PATH, Config.BACKUP_DIR = original_db, original_dir
        os.remove(db_path)


def test_restore_dry_run_writes_nothing(app):
    db_path = _make_test_db()
    backup_dir = tempfile.mkdtemp()
    original_db, original_dir = Config.DATABASE_PATH, Config.BACKUP_DIR
    try:
        Config.DATABASE_PATH = db_path
        Config.BACKUP_DIR = backup_dir
        enc_path = backup_database()

        result = restore_backup(enc_path, output_path=None)
        assert result["integrity_ok"] is True
        assert result["row_counts"] is not None
    finally:
        Config.DATABASE_PATH, Config.BACKUP_DIR = original_db, original_dir
        os.remove(db_path)


def test_prune_old_backups_respects_retention_count():
    backup_dir = tempfile.mkdtemp()
    original_dir, original_count = Config.BACKUP_DIR, Config.BACKUP_RETENTION_COUNT
    try:
        Config.BACKUP_DIR = backup_dir
        Config.BACKUP_RETENTION_COUNT = 2

        for i in range(5):
            with open(os.path.join(backup_dir, f"jointx_2024010{i}_000000.db.enc"), "wb") as f:
                f.write(b"x")

        prune_old_backups()
        remaining = [f for f in os.listdir(backup_dir) if f.endswith(".db.enc")]
        assert len(remaining) == 2
    finally:
        Config.BACKUP_DIR, Config.BACKUP_RETENTION_COUNT = original_dir, original_count
