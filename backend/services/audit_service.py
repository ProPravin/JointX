"""
Audit trail for security-relevant actions (spec: Production-grade RBAC #5).
Every write here is append-only — nothing in this codebase updates or
deletes an audit_log row.
"""
from database.database import get_cursor
from backend.utils.helpers import to_json


def log_action(worker_id, action: str, entity_type: str = None, entity_id: int = None, details: dict = None):
    with get_cursor(commit=True) as cur:
        cur.execute(
            """INSERT INTO audit_log (worker_id, action, entity_type, entity_id, details_json)
               VALUES (?, ?, ?, ?, ?)""",
            (worker_id, action, entity_type, entity_id, to_json(details) if details else None),
        )


def list_audit_log(limit: int = 200, action: str = None) -> list:
    with get_cursor() as cur:
        if action:
            cur.execute(
                """SELECT a.*, w.username, w.full_name
                   FROM audit_log a LEFT JOIN healthcare_workers w ON w.id = a.worker_id
                   WHERE a.action = ? ORDER BY a.created_at DESC LIMIT ?""",
                (action, limit),
            )
        else:
            cur.execute(
                """SELECT a.*, w.username, w.full_name
                   FROM audit_log a LEFT JOIN healthcare_workers w ON w.id = a.worker_id
                   ORDER BY a.created_at DESC LIMIT ?""",
                (limit,),
            )
        rows = cur.fetchall()
    return [dict(r) for r in rows]
