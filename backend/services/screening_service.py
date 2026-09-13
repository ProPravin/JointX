"""Screening session lifecycle: create, fetch, update status, complete."""
from database.database import get_cursor
from backend.utils.error_handler import JointXError
from backend.utils.helpers import from_json


def start_screening(patient_id: int, performed_by: int, is_demo: bool = False) -> dict:
    with get_cursor(commit=True) as cur:
        cur.execute("SELECT id FROM patients WHERE id = ?", (patient_id,))
        if not cur.fetchone():
            raise JointXError("Patient not found", status_code=404)
        cur.execute(
            """INSERT INTO screenings (patient_id, performed_by, status, is_demo)
               VALUES (?, ?, 'IN_PROGRESS', ?)""",
            (patient_id, performed_by, int(is_demo)),
        )
        screening_id = cur.lastrowid
    return get_screening(screening_id)


def get_screening(screening_id: int) -> dict:
    with get_cursor() as cur:
        cur.execute("SELECT * FROM screenings WHERE id = ?", (screening_id,))
        row = cur.fetchone()
    if not row:
        raise JointXError("Screening not found", status_code=404)
    return dict(row)


def update_screening_status(screening_id: int, status: str):
    with get_cursor(commit=True) as cur:
        cur.execute(
            "UPDATE screenings SET status = ? WHERE id = ?", (status, screening_id)
        )


def complete_screening(screening_id: int):
    with get_cursor(commit=True) as cur:
        cur.execute(
            """UPDATE screenings SET status = 'COMPLETED', completed_at = datetime('now')
               WHERE id = ?""",
            (screening_id,),
        )


def get_full_screening_record(screening_id: int) -> dict:
    """Aggregate everything about a screening for the results/report screens."""
    screening = get_screening(screening_id)

    with get_cursor() as cur:
        cur.execute("SELECT * FROM patients WHERE id = ?", (screening["patient_id"],))
        patient = dict(cur.fetchone() or {})

        cur.execute("SELECT * FROM questionnaire WHERE screening_id = ?", (screening_id,))
        row = cur.fetchone()
        questionnaire = dict(row) if row else None

        cur.execute("SELECT * FROM gait_features WHERE screening_id = ?", (screening_id,))
        row = cur.fetchone()
        gait = dict(row) if row else None

        cur.execute("SELECT * FROM imu_features WHERE screening_id = ?", (screening_id,))
        row = cur.fetchone()
        imu = dict(row) if row else None

        cur.execute("SELECT * FROM functional_features WHERE screening_id = ?", (screening_id,))
        row = cur.fetchone()
        functional = dict(row) if row else None

        cur.execute("SELECT * FROM predictions WHERE screening_id = ?", (screening_id,))
        row = cur.fetchone()
        prediction = dict(row) if row else None

        cur.execute("SELECT * FROM shap_explanations WHERE screening_id = ?", (screening_id,))
        row = cur.fetchone()
        shap_row = dict(row) if row else None
        shap_explanation = from_json(shap_row["explanation_json"]) if shap_row else None

        cur.execute("SELECT * FROM healthcare_reviews WHERE screening_id = ?", (screening_id,))
        row = cur.fetchone()
        review = dict(row) if row else None

        cur.execute("SELECT * FROM referrals WHERE screening_id = ? ORDER BY created_at DESC", (screening_id,))
        referrals = [dict(r) for r in cur.fetchall()]

    return {
        "screening": screening,
        "patient": patient,
        "questionnaire": questionnaire,
        "gait_features": gait,
        "imu_features": imu,
        "functional_features": functional,
        "prediction": prediction,
        "shap_explanation": shap_explanation,
        "review": review,
        "referrals": referrals,
    }
