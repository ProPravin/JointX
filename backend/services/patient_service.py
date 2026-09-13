"""Patient registration, search, and profile retrieval."""
from database.database import get_cursor
from backend.utils.helpers import generate_patient_code, compute_bmi
from backend.utils.validators import require_fields, validate_range, validate_sex
from backend.utils.error_handler import JointXError


def create_patient(data: dict, registered_by: int) -> dict:
    require_fields(data, ["full_name"])
    validate_sex(data.get("sex"))
    validate_range(data.get("age"), 0, 120, "age")
    validate_range(data.get("height_cm"), 30, 250, "height_cm")
    validate_range(data.get("weight_kg"), 2, 400, "weight_kg")

    patient_code = data.get("patient_code") or generate_patient_code()

    with get_cursor(commit=True) as cur:
        cur.execute(
            """INSERT INTO patients
               (patient_code, full_name, age, sex, height_cm, weight_kg,
                village_or_area, contact_phone, registered_by)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                patient_code,
                data["full_name"],
                data.get("age"),
                data.get("sex"),
                data.get("height_cm"),
                data.get("weight_kg"),
                data.get("village_or_area"),
                data.get("contact_phone"),
                registered_by,
            ),
        )
        patient_id = cur.lastrowid

    return get_patient(patient_id)


def get_patient(patient_id: int) -> dict:
    with get_cursor() as cur:
        cur.execute("SELECT * FROM patients WHERE id = ?", (patient_id,))
        row = cur.fetchone()
    if not row:
        raise JointXError("Patient not found", status_code=404)
    row = dict(row)
    row["bmi"] = compute_bmi(row.get("height_cm"), row.get("weight_kg"))
    return row


def search_patients(query: str = "", limit: int = 50) -> list:
    with get_cursor() as cur:
        if query:
            like = f"%{query}%"
            cur.execute(
                """SELECT * FROM patients
                   WHERE full_name LIKE ? OR patient_code LIKE ? OR village_or_area LIKE ?
                   ORDER BY created_at DESC LIMIT ?""",
                (like, like, like, limit),
            )
        else:
            cur.execute("SELECT * FROM patients ORDER BY created_at DESC LIMIT ?", (limit,))
        rows = cur.fetchall()
    return [dict(r) for r in rows]


def get_patient_screening_history(patient_id: int) -> list:
    with get_cursor() as cur:
        cur.execute(
            """SELECT s.*, p.risk_label, p.risk_score
               FROM screenings s
               LEFT JOIN predictions p ON p.screening_id = s.id
               WHERE s.patient_id = ?
               ORDER BY s.started_at DESC""",
            (patient_id,),
        )
        rows = cur.fetchall()
    return [dict(r) for r in rows]
