-- Central sync server schema (reference implementation).
--
-- This is deliberately a THIN ingestion store, not a full analytics
-- warehouse: it records exactly what each field device pushed, verbatim,
-- keyed by (device_id, entity_type, entity_id) so a re-send of the same
-- screening (e.g. after a retry) overwrites rather than duplicates.
--
-- For a real multi-site production deployment, swap SQLite for Postgres
-- (this schema is plain ANSI-ish SQL and should port with minimal changes)
-- and build proper normalized reporting tables/views on top of
-- synced_records.payload_json once you know what your BI tooling needs --
-- don't try to guess that shape in advance.

CREATE TABLE IF NOT EXISTS devices (
    device_id       TEXT PRIMARY KEY,
    first_seen_at   TEXT NOT NULL DEFAULT (datetime('now')),
    last_seen_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS synced_records (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id       TEXT NOT NULL REFERENCES devices(device_id),
    entity_type     TEXT NOT NULL,   -- 'screening', matching sync_queue.entity_type on the field device
    entity_id       INTEGER NOT NULL,  -- the SOURCE device's own local ID -- not globally unique by itself
    payload_json    TEXT NOT NULL,   -- verbatim record as pushed by sync/sync_service.py
    received_at     TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (device_id, entity_type, entity_id)
);

CREATE INDEX IF NOT EXISTS idx_synced_records_device ON synced_records(device_id);
CREATE INDEX IF NOT EXISTS idx_synced_records_received ON synced_records(received_at);
