"""
Patient registration, search, and profile retrieval.

This is the ONLY module (besides backend/utils/crypto.py itself) allowed to
read or write patients.full_name / contact_phone / village_or_area directly
-- every other module that needs a patient's decrypted details must go
through get_patient()/search_patients() here, or call decrypt_patient_row()
on a raw row it already has (see backend/services/screening_service.py and
backend/routes/screening_routes.py for the two other legitimate raw-SQL
readers of the patients table, which both import decrypt_patient_row from
here rather than duplicating decryption logic).
"""
from database.database import get_cursor
from backend.utils.helpers import generate_patient_code, compute_bmi
from backend.utils.validators import require_fields, validate_range, validate_sex
from backend.utils.error_handler import JointXError
from backend.utils import crypto

ENCRYPTED_FIELDS = ("full_name", "contact_phone", "village_or_area")


def decrypt_patient_row(row: dict) -> dict:
    """
    Returns a copy of a raw patients row with full_name/contact_phone/
    village_or_area decrypted. Safe to call on a dict that's already
    decrypted (Fernet ciphertext is distinguishable, but callers should
    still only ever call this once per row) -- used by every module that
    reads the patients table directly instead of through this service.
    """
    row = dict(row)
    for field in ENCRYPTED_FIELDS:
        if field in row:
            row[field] = crypto.decrypt_field(row[field])
    return row


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
               (patient_code, full_name, full_name_hash, age, sex, height_cm, weight_kg,
                village_or_area, contact_phone, contact_phone_hash, facility_name, registered_by)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                patient_code,
                crypto.encrypt_field(data["full_name"]),
                crypto.hash_field(data["full_name"]),
                data.get("age"),
                data.get("sex"),
                data.get("height_cm"),
                data.get("weight_kg"),
                crypto.encrypt_field(data.get("village_or_area")),
                crypto.encrypt_field(data.get("contact_phone")),
                crypto.hash_field(data.get("contact_phone")),
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
    row = decrypt_patient_row(row)
    row["bmi"] = compute_bmi(row.get("height_cm"), row.get("weight_kg"))
    return row


def search_patients(query: str = "", facility_name: str = None, limit: int = 50) -> list:
    """
    facility_name, when given, restricts results to that facility — used to
    scope Healthcare Worker access to their own facility's patients (spec:
    Production-grade RBAC #3). Doctors/Reviewers and Admins pass None to see
    across facilities.

    SEARCH BEHAVIOUR CHANGED BY ENCRYPTION (spec: P1 data layer #4): full_name
    and contact_phone are ciphertext in the database, so a partial/fuzzy LIKE
    match against them is no longer possible without decrypting every row
    (which would defeat the point of encrypting them). `query` now matches:
      - patient_code: partial match (LIKE), unencrypted, works as before
      - full_name / contact_phone: EXACT match only, via the deterministic
        hash columns (full_name_hash / contact_phone_hash)
    village_or_area is no longer searchable at all (no hash column for it --
    it wasn't a query target worth the extra dedup-key surface area).
    """
    clauses = []
    params = []
    if query:
        like = f"%{query}%"
        name_hash = crypto.hash_field(query)
        clauses.append("(patient_code LIKE ? OR full_name_hash = ? OR contact_phone_hash = ?)")
        params += [like, name_hash, name_hash]
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
    return [decrypt_patient_row(r) for r in rows]


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
