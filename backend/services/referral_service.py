"""Referral creation and status tracking (spec section 14)."""
from database.database import get_cursor
from backend.utils.validators import require_fields, validate_choice
from backend.utils.error_handler import JointXError

VALID_STATUSES = [
    "NOT_REFERRED",
    "REFERRAL_CREATED",
    "PENDING",
    "TELECONSULT_COMPLETED",
    "CLINICAL_VISIT_COMPLETED",
    "FOLLOW_UP_REQUIRED",
    "CLOSED",
]


def create_referral(screening_id: int, created_by: int, data: dict) -> dict:
    status = data.get("status", "REFERRAL_CREATED")
    validate_choice(status, VALID_STATUSES, "status")

    with get_cursor(commit=True) as cur:
        cur.execute(
            """INSERT INTO referrals (screening_id, status, notes, created_by)
               VALUES (?, ?, ?, ?)""",
            (screening_id, status, data.get("notes", ""), created_by),
        )
        referral_id = cur.lastrowid

    return get_referral(referral_id)


def get_referral(referral_id: int) -> dict:
    with get_cursor() as cur:
        cur.execute("SELECT * FROM referrals WHERE id = ?", (referral_id,))
        row = cur.fetchone()
    if not row:
        raise JointXError("Referral not found", status_code=404)
    return dict(row)


def list_referrals(status: str = None) -> list:
    with get_cursor() as cur:
        if status:
            validate_choice(status, VALID_STATUSES, "status")
            cur.execute(
                """SELECT r.*, s.patient_id, p.full_name, p.patient_code
                   FROM referrals r
                   JOIN screenings s ON s.id = r.screening_id
                   JOIN patients p ON p.id = s.patient_id
                   WHERE r.status = ? ORDER BY r.created_at DESC""",
                (status,),
            )
        else:
            cur.execute(
                """SELECT r.*, s.patient_id, p.full_name, p.patient_code
                   FROM referrals r
                   JOIN screenings s ON s.id = r.screening_id
                   JOIN patients p ON p.id = s.patient_id
                   ORDER BY r.created_at DESC"""
            )
        rows = cur.fetchall()
    return [dict(r) for r in rows]


def update_referral(referral_id: int, data: dict) -> dict:
    require_fields(data, [])
    fields, values = [], []
    if "status" in data:
        validate_choice(data["status"], VALID_STATUSES, "status")
        fields.append("status = ?")
        values.append(data["status"])
    if "notes" in data:
        fields.append("notes = ?")
        values.append(data["notes"])
    if not fields:
        return get_referral(referral_id)

    fields.append("updated_at = datetime('now')")
    values.append(referral_id)

    with get_cursor(commit=True) as cur:
        cur.execute(f"UPDATE referrals SET {', '.join(fields)} WHERE id = ?", values)

    return get_referral(referral_id)
