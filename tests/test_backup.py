import gzip
import os
import sqlite3
import tempfile

from config.settings import Config
from tools.backup_db import backup_database, prune_old_backups


def test_backup_database_creates_valid_gzip_snapshot():
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, name TEXT)")
    conn.execute("INSERT INTO t (name) VALUES ('hello')")
    conn.commit()
    conn.close()

    backup_dir = tempfile.mkdtemp()
    original_db, original_dir = Config.DATABASE_PATH, Config.BACKUP_DIR
    try:
        Config.DATABASE_PATH = db_path
        Config.BACKUP_DIR = backup_dir

        gz_path = backup_database()
        assert os.path.exists(gz_path)
        assert gz_path.endswith(".db.gz")

        # Decompress and verify the data round-tripped correctly.
        restored_path = gz_path[:-3]
        with gzip.open(gz_path, "rb") as f_in, open(restored_path, "wb") as f_out:
            f_out.write(f_in.read())
        restored = sqlite3.connect(restored_path)
        row = restored.execute("SELECT name FROM t").fetchone()
        restored.close()
        assert row[0] == "hello"
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
            with open(os.path.join(backup_dir, f"jointx_2024010{i}_000000.db.gz"), "wb") as f:
                f.write(b"x")

        prune_old_backups()
        remaining = [f for f in os.listdir(backup_dir) if f.endswith(".db.gz")]
        assert len(remaining) == 2
    finally:
        Config.BACKUP_DIR, Config.BACKUP_RETENTION_COUNT = original_dir, original_count
