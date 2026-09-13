"""
SQLite connection management for JointX.

Offline-first: this is the ONLY persistence layer required for the app to
function with zero connectivity. All writes are local; sync/ handles pushing
to a remote endpoint opportunistically.
"""
import os
import sqlite3
import threading
from contextlib import contextmanager

from config.settings import Config

_local = threading.local()


def _row_factory(cursor, row):
    return {col[0]: row[idx] for idx, col in enumerate(cursor.description)}


def get_connection():
    """Return a thread-local SQLite connection with foreign keys enabled."""
    if not hasattr(_local, "conn"):
        os.makedirs(os.path.dirname(Config.DATABASE_PATH), exist_ok=True)
        conn = sqlite3.connect(Config.DATABASE_PATH, check_same_thread=False)
        conn.row_factory = _row_factory
        conn.execute("PRAGMA foreign_keys = ON")
        _local.conn = conn
    return _local.conn


@contextmanager
def get_cursor(commit=False):
    conn = get_connection()
    cur = conn.cursor()
    try:
        yield cur
        if commit:
            conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()


def init_db():
    """Create all tables from database/schema.sql if they do not exist."""
    conn = get_connection()
    with open(Config.SCHEMA_PATH, "r") as f:
        schema = f.read()
    conn.executescript(schema)
    conn.commit()


def seed_default_worker():
    """Create a default healthcare-worker login for first run (demo use)."""
    from backend.utils.security import hash_password

    with get_cursor(commit=True) as cur:
        cur.execute("SELECT COUNT(*) as c FROM healthcare_workers")
        count = cur.fetchone()["c"]
        if count == 0:
            cur.execute(
                """INSERT INTO healthcare_workers
                   (username, password_hash, full_name, role, facility_name)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    "admin",
                    hash_password("changeme123"),
                    "Default Administrator",
                    "ADMIN",
                    "JointX Demo PHC",
                ),
            )
