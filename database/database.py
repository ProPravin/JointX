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
    """
    Return a thread-local SQLite connection with foreign keys enabled.
    Re-opens the connection if Config.DATABASE_PATH has changed since the
    cached one was created (e.g. each test run pointing at its own temp DB)
    rather than silently keeping the old file open forever.
    """
    if not hasattr(_local, "conn") or getattr(_local, "conn_path", None) != Config.DATABASE_PATH:
        if hasattr(_local, "conn"):
            _local.conn.close()
        os.makedirs(os.path.dirname(Config.DATABASE_PATH), exist_ok=True)
        conn = sqlite3.connect(Config.DATABASE_PATH, check_same_thread=False)
        conn.row_factory = _row_factory
        conn.execute("PRAGMA foreign_keys = ON")
        _local.conn = conn
        _local.conn_path = Config.DATABASE_PATH
    return _local.conn


def close_connection():
    """Close and drop the cached thread-local connection, if any (tests use
    this to release the SQLite file handle before deleting a temp DB —
    required on Windows, which refuses to delete an open file)."""
    if hasattr(_local, "conn"):
        _local.conn.close()
        del _local.conn
        del _local.conn_path


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


# Columns added to tables after their initial release. schema.sql's
# CREATE TABLE IF NOT EXISTS only applies to brand-new databases, so an
# existing database needs these ALTER TABLE statements run explicitly --
# otherwise a schema bump silently leaves old databases without the new
# columns instead of losing data outright, which is just as dangerous.
_COLUMN_MIGRATIONS = {
    "healthcare_reviews": [
        ("label_source", "TEXT"),
        ("kl_grade_value", "INTEGER"),
        ("radiograph_ref", "TEXT"),
        ("acr_criteria_json", "TEXT"),
        ("reviewer_label_blind", "TEXT"),
        ("prediction_revealed_at", "TEXT"),
    ],
    "predictions": [
        ("refused", "INTEGER NOT NULL DEFAULT 0"),
        ("refusal_reason", "TEXT"),
    ],
}


def _apply_column_migrations(conn):
    # PRAGMA table_info rows go through the connection's row_factory (a dict
    # keyed by column name here), not a plain tuple -- index by "name", not
    # by position.
    for table, columns in _COLUMN_MIGRATIONS.items():
        existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
        for name, ddl_type in columns:
            if name not in existing:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {ddl_type}")


def init_db():
    """Create all tables from database/schema.sql if they do not exist, then
    apply any column migrations needed to bring an existing database's tables
    up to date without losing rows."""
    conn = get_connection()
    with open(Config.SCHEMA_PATH, "r") as f:
        schema = f.read()
    conn.executescript(schema)
    _apply_column_migrations(conn)
    conn.commit()


def seed_default_worker():
    """
    Create one seeded login per role tier for first run (demo use), so
    role-based access can actually be exercised end-to-end without an
    admin-account-creation UI:
      - admin / changeme123           (tier: admin)
      - asha_field / AshaField@123    (tier: worker — screening capture)
      - dr_reviewer / DrReview@123    (tier: reviewer — clinical review)
    Change all three before any real deployment — see README.md.

    Only runs when Config.DEMO_MODE is true. A production deployment must
    create its first Admin via the `flask create-admin` CLI command instead
    (see app.py) and provision every other account through that Admin.
    """
    if not Config.DEMO_MODE:
        return

    from backend.utils.security import hash_password

    with get_cursor(commit=True) as cur:
        cur.execute("SELECT COUNT(*) as c FROM healthcare_workers")
        count = cur.fetchone()["c"]
        if count == 0:
            seeded_workers = [
                ("admin", "changeme123", "Default Administrator", "ADMIN"),
                ("asha_field", "AshaField@123", "ASHA Field Worker", "ASHA"),
                ("dr_reviewer", "DrReview@123", "Dr. Reviewer", "DOCTOR"),
            ]
            for username, password, full_name, role in seeded_workers:
                cur.execute(
                    """INSERT INTO healthcare_workers
                       (username, password_hash, full_name, role, facility_name)
                       VALUES (?, ?, ?, ?, ?)""",
                    (username, hash_password(password), full_name, role, "JointX Demo PHC"),
                )
