"""
Admin-only account management (spec: Production-grade RBAC #1/#3).
Real deployments provision every non-first account through these functions
(via backend/routes/admin_routes.py), never through the public /register
endpoint, which is disabled outside DEMO_MODE.
"""
from database.database import get_cursor
from backend.utils.security import hash_password, validate_password_strength
from backend.utils.validators import ValidationError
from config.roles import tier_for_role, label_for_role, ROLE_TIERS


def create_worker(username: str, password: str, full_name: str, role: str, facility_name: str, created_by: int) -> dict:
    role = (role or "").upper()
    if role not in ROLE_TIERS:
        raise ValidationError(f"role must be one of {list(ROLE_TIERS)}")

    validate_password_strength(password)

    with get_cursor() as cur:
        cur.execute("SELECT id FROM healthcare_workers WHERE username = ?", (username,))
        if cur.fetchone():
            raise ValidationError("That username is already taken")

    with get_cursor(commit=True) as cur:
        cur.execute(
            """INSERT INTO healthcare_workers (username, password_hash, full_name, role, facility_name, created_by)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (username, hash_password(password), full_name, role, facility_name, created_by),
        )
        worker_id = cur.lastrowid

    return get_worker(worker_id)


def get_worker(worker_id: int) -> dict:
    with get_cursor() as cur:
        cur.execute(
            "SELECT id, username, full_name, role, facility_name, is_active, created_by, created_at FROM healthcare_workers WHERE id = ?",
            (worker_id,),
        )
        row = cur.fetchone()
    if not row:
        raise ValidationError("Worker not found")
    worker = dict(row)
    worker["role_tier"] = tier_for_role(worker["role"])
    worker["role_label"] = label_for_role(worker["role"])
    return worker


def list_workers() -> list:
    with get_cursor() as cur:
        cur.execute(
            """SELECT id, username, full_name, role, facility_name, is_active, created_by, created_at
               FROM healthcare_workers ORDER BY created_at DESC"""
        )
        rows = [dict(r) for r in cur.fetchall()]
    for worker in rows:
        worker["role_tier"] = tier_for_role(worker["role"])
        worker["role_label"] = label_for_role(worker["role"])
    return rows


def set_worker_active(worker_id: int, is_active: bool) -> dict:
    with get_cursor(commit=True) as cur:
        cur.execute("UPDATE healthcare_workers SET is_active = ? WHERE id = ?", (1 if is_active else 0, worker_id))
    return get_worker(worker_id)


def reset_worker_password(worker_id: int, new_password: str) -> dict:
    validate_password_strength(new_password)
    with get_cursor(commit=True) as cur:
        cur.execute(
            """UPDATE healthcare_workers
               SET password_hash = ?, failed_login_attempts = 0, locked_until = NULL
               WHERE id = ?""",
            (hash_password(new_password), worker_id),
        )
    return get_worker(worker_id)
