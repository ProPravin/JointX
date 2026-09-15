"""
Central sync server -- REFERENCE IMPLEMENTATION.

This is the "other end" of the sync each field device already performs
(backend/services/sync_service.py -> sync/sync_service.py -> here). It exists
so JointX's existing offline-first sync client has something real to talk to,
proving the round trip end to end -- it is intentionally minimal, not a full
program-management backend.

Run standalone (separate from the main JointX app -- this is meant to run on
a central server, not on the field device/Pi):
    pip install -r central_server/requirements.txt
    python central_server/app.py

Then point each field device's .env at it:
    JOINTX_SYNC_ENDPOINT=http://<central-host>:5050/api/sync/ingest
    JOINTX_SYNC_API_KEY=<same value as CENTRAL_API_KEY below>

PRODUCTION NOTES (do this before relying on it):
  - Swap CENTRAL_DB_PATH's SQLite file for a real Postgres database -- SQLite
    does not handle many simultaneous writers well, and a central server for
    a multi-site deployment needs that.
  - Put this behind HTTPS (a reverse proxy like nginx/Caddy terminating TLS)
    -- it is only ever run over plain HTTP by default, which is fine for
    local testing and NOT fine once real patient data crosses a network.
  - Give each facility its own API key (not one shared key for every device)
    so a compromised device's key can be revoked individually.
"""
import os
import sqlite3
from datetime import datetime

from flask import Flask, request, jsonify

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CENTRAL_DB_PATH = os.environ.get("CENTRAL_DB_PATH", os.path.join(BASE_DIR, "central.db"))
CENTRAL_API_KEY = os.environ.get("CENTRAL_API_KEY", "")  # required in any real deployment
SCHEMA_PATH = os.path.join(BASE_DIR, "schema.sql")

app = Flask(__name__)


def get_db():
    conn = sqlite3.connect(CENTRAL_DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_db()
    with open(SCHEMA_PATH) as f:
        conn.executescript(f.read())
    conn.commit()
    conn.close()


def _check_auth():
    if not CENTRAL_API_KEY:
        # Explicitly loud rather than silently open -- an unset key on a
        # reference server should not be mistaken for "no auth needed".
        return False, "Server misconfigured: CENTRAL_API_KEY is not set"
    auth = request.headers.get("Authorization", "")
    if auth != f"Bearer {CENTRAL_API_KEY}":
        return False, "Invalid or missing API key"
    return True, None


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


@app.route("/api/sync/ingest", methods=["POST"])
def ingest():
    ok, error = _check_auth()
    if not ok:
        return jsonify({"success": False, "error": error}), 401

    device_id = request.headers.get("X-Device-Id")
    entity_type = request.headers.get("X-Entity-Type")
    entity_id = request.headers.get("X-Entity-Id")
    if not (device_id and entity_type and entity_id):
        return jsonify({"success": False, "error": "Missing X-Device-Id / X-Entity-Type / X-Entity-Id headers"}), 400

    payload_json = request.get_data(as_text=True)
    if not payload_json:
        return jsonify({"success": False, "error": "Empty request body"}), 400

    conn = get_db()
    try:
        now = datetime.now().isoformat(sep=" ", timespec="seconds")
        conn.execute(
            """INSERT INTO devices (device_id, first_seen_at, last_seen_at) VALUES (?, ?, ?)
               ON CONFLICT(device_id) DO UPDATE SET last_seen_at = excluded.last_seen_at""",
            (device_id, now, now),
        )
        conn.execute(
            """INSERT INTO synced_records (device_id, entity_type, entity_id, payload_json, received_at)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(device_id, entity_type, entity_id)
               DO UPDATE SET payload_json = excluded.payload_json, received_at = excluded.received_at""",
            (device_id, entity_type, int(entity_id), payload_json, now),
        )
        conn.commit()
    finally:
        conn.close()

    return jsonify({"success": True})


@app.route("/api/sync/records", methods=["GET"])
def list_records():
    """Basic listing for verifying ingestion during testing/demos -- add real auth/pagination before production use."""
    ok, error = _check_auth()
    if not ok:
        return jsonify({"success": False, "error": error}), 401

    conn = get_db()
    rows = conn.execute(
        "SELECT device_id, entity_type, entity_id, received_at FROM synced_records ORDER BY received_at DESC LIMIT 100"
    ).fetchall()
    conn.close()
    return jsonify({"success": True, "data": [dict(r) for r in rows]})


if __name__ == "__main__":
    if not CENTRAL_API_KEY:
        print("WARNING: CENTRAL_API_KEY is not set -- every request will be rejected with 401.")
        print("Set it via: set CENTRAL_API_KEY=your-key-here  (PowerShell: $env:CENTRAL_API_KEY=\"your-key-here\")")
    init_db()
    app.run(host="0.0.0.0", port=int(os.environ.get("CENTRAL_PORT", "5050")))
