"""Healthcare-worker review of a screening's AI risk result (spec section Q)."""
from database.database import get_cursor
from backend.utils.validators import require_fields, validate_choice, ValidationError
from config.model_config import RISK_LABELS


def submit_review(screening_id: int, reviewed_by: int, data: dict) -> dict:
    require_fields(data, ["notes"])
    clinician_label = data.get("clinician_label")
    if clinician_label is not None:
        validate_choice(clinician_label, RISK_LABELS, "clinician_label")
    elif data.get("agrees_with_model") == 0:
        raise ValidationError(
            "clinician_label is required when disagreeing with the model, "
            "so the true risk category is recorded for future training data."
        )

    with get_cursor(commit=True) as cur:
        cur.execute("DELETE FROM healthcare_reviews WHERE screening_id = ?", (screening_id,))
        cur.execute(
            """INSERT INTO healthcare_reviews
               (screening_id, reviewed_by, notes, agrees_with_model, clinician_label)
               VALUES (?, ?, ?, ?, ?)""",
            (screening_id, reviewed_by, data["notes"], data.get("agrees_with_model"), clinician_label),
        )
        cur.execute("UPDATE screenings SET status = 'REVIEWED' WHERE id = ?", (screening_id,))

    with get_cursor() as cur:
        cur.execute("SELECT * FROM healthcare_reviews WHERE screening_id = ?", (screening_id,))
        return dict(cur.fetchone())
