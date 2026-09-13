"""
Store-and-forward sync orchestration (spec sections 15 and 27). Delegates
the actual network transmission to sync/sync_service.py so the backend
service layer stays storage/queue-focused and the sync/ package stays
network-focused and independently testable.
"""
from database.database import get_cursor
from backend.utils.helpers import to_json
from backend.services.screening_service import get_full_screening_record
from sync.sync_service import push_batch
from sync.connectivity import is_online


def enqueue_screening_for_sync(screening_id: int):
    record = get_full_screening_record(screening_id)
    with get_cursor(commit=True) as cur:
        cur.execute(
            """INSERT INTO sync_queue (entity_type, entity_id, payload_json, status)
               VALUES ('screening', ?, ?, 'PENDING')""",
            (screening_id, to_json(record)),
        )


def get_pending_queue(limit: int = 100) -> list:
    with get_cursor() as cur:
        cur.execute(
            "SELECT * FROM sync_queue WHERE status = 'PENDING' ORDER BY created_at LIMIT ?",
            (limit,),
        )
        return [dict(r) for r in cur.fetchall()]


def get_sync_summary() -> dict:
    with get_cursor() as cur:
        cur.execute("SELECT COUNT(*) c FROM sync_queue WHERE status = 'PENDING'")
        pending = cur.fetchone()["c"]
        cur.execute("SELECT MAX(synced_at) t FROM sync_queue WHERE status = 'SYNCED'")
        last_sync = cur.fetchone()["t"]
    return {"pending_count": pending, "last_synced_at": last_sync, "online": is_online()}


def run_sync() -> dict:
    """Attempts to push all pending records. Never raises -- returns a summary."""
    if not is_online():
        return {"attempted": 0, "synced": 0, "failed": 0, "reason": "offline"}

    items = get_pending_queue()
    synced, failed = 0, 0
    for item in items:
        ok, error = push_batch(item)
        with get_cursor(commit=True) as cur:
            if ok:
                cur.execute(
                    "UPDATE sync_queue SET status='SYNCED', synced_at=datetime('now') WHERE id=?",
                    (item["id"],),
                )
                synced += 1
            else:
                cur.execute(
                    """UPDATE sync_queue SET attempts = attempts + 1, last_error = ?
                       WHERE id = ?""",
                    (error, item["id"]),
                )
                failed += 1

    return {"attempted": len(items), "synced": synced, "failed": failed}
