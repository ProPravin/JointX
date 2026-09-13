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

    # facility_name is copied from the registering worker's own account, not
    # taken from client input, so a worker can never register a patient into
    # a facility they don't belong to.
    with get_cursor() as cur:
        cur.execute("SELECT facility_name FROM healthcare_workers WHERE id = ?", (registered_by,))
        worker_row = cur.fetchone()
    facility_name = worker_row["facility_name"] if worker_row else None

    with get_cursor(commit=True) as cur:
        cur.execute(
            """INSERT INTO patients
               (patient_code, full_name, age, sex, height_cm, weight_kg,
                village_or_area, contact_phone, facility_name, registered_by)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                patient_code,
                data["full_name"],
                data.get("age"),
                data.get("sex"),
                data.get("height_cm"),
                data.get("weight_kg"),
                data.get("village_or_area"),
                data.get("contact_phone"),
                facility_name,
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


def search_patients(query: str = "", facility_name: str = None, limit: int = 50) -> list:
    """
    facility_name, when given, restricts results to that facility — used to
    scope Healthcare Worker access to their own facility's patients (spec:
    Production-grade RBAC #3). Doctors/Reviewers and Admins pass None to see
    across facilities.
    """
    clauses = []
    params = []
    if query:
        like = f"%{query}%"
        clauses.append("(full_name LIKE ? OR patient_code LIKE ? OR village_or_area LIKE ?)")
        params += [like, like, like]
    if facility_name is not None:
        clauses.append("facility_name = ?")
        params.append(facility_name)

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    with get_cursor() as cur:
        cur.execute(
            f"SELECT * FROM patients {where} ORDER BY created_at DESC LIMIT ?",
            (*params, limit),
        )
        rows = cur.fetchall()
    return [dict(r) for r in rows]


def get_patient_risk_history(patient_id: int) -> list:
    """
    Chronological (oldest first) list of {screening_id, started_at, risk_label,
    risk_score} for this patient's screenings that have a prediction — the
    real, DB-backed data behind a longitudinal OA-risk trend chart. Screenings
    without a prediction yet are omitted rather than plotted as zero.
    """
    with get_cursor() as cur:
        cur.execute(
            """SELECT s.id AS screening_id, s.started_at, p.risk_label, p.risk_score
               FROM screenings s
               JOIN predictions p ON p.screening_id = s.id
               WHERE s.patient_id = ?
               ORDER BY s.started_at ASC""",
            (patient_id,),
        )
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
