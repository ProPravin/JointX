"""
Healthcare-worker review of a screening's AI risk result, using a BLINDED
review workflow (spec: Data Integrity #A1).

Why blinding matters: a reviewer who sees the model's prediction before
forming their own opinion is subject to automation bias -- agreement rates
climb even when the model is wrong, because "agree" is one tap and disagreeing
requires the reviewer to commit to and justify an alternative. A label
recorded after the prediction was seen cannot be trusted as independent
ground truth, so it is not eligible as a test-set label (see
training/export_dataset.py).

The workflow is three steps, enforced in order by this module:
  1. submit_blind_review() -- reviewer records reviewer_label_blind BEFORE
     seeing the model's output.
  2. reveal_prediction()   -- the model's prediction is shown; this is
     timestamped (prediction_revealed_at) and cannot happen before step 1.
  3. submit_review()       -- the reviewer finalizes clinical notes,
     agreement, and (if available) an evidence-backed label_source
     (kl_grade / acr_clinical / clinician_impression / model_confirmed).
     This cannot happen before step 2.
"""
from database.database import get_cursor
from backend.utils.validators import require_fields, validate_choice, ValidationError
from config.model_config import RISK_LABELS

LABEL_SOURCES = ["kl_grade", "acr_clinical", "clinician_impression", "model_confirmed"]


def _get_review_row(screening_id: int):
    with get_cursor() as cur:
        cur.execute("SELECT * FROM healthcare_reviews WHERE screening_id = ?", (screening_id,))
        row = cur.fetchone()
    return dict(row) if row else None


def submit_blind_review(screening_id: int, reviewer_id: int, reviewer_label_blind: str) -> dict:
    validate_choice(reviewer_label_blind, RISK_LABELS, "reviewer_label_blind")

    existing = _get_review_row(screening_id)
    if existing and existing.get("prediction_revealed_at"):
        raise ValidationError(
            "The model's prediction has already been revealed for this screening; "
            "a blind label recorded now would no longer be independent."
        )

    with get_cursor(commit=True) as cur:
        if existing:
            cur.execute(
                "UPDATE healthcare_reviews SET reviewer_label_blind = ?, reviewed_by = ? WHERE screening_id = ?",
                (reviewer_label_blind, reviewer_id, screening_id),
            )
        else:
            cur.execute(
                """INSERT INTO healthcare_reviews (screening_id, reviewed_by, reviewer_label_blind)
                   VALUES (?, ?, ?)""",
                (screening_id, reviewer_id, reviewer_label_blind),
            )

    return _get_review_row(screening_id)


def reveal_prediction(screening_id: int) -> dict:
    review = _get_review_row(screening_id)
    if not review or not review.get("reviewer_label_blind"):
        raise ValidationError(
            "Submit your blind risk assessment before revealing the model's prediction."
        )
    if review.get("prediction_revealed_at"):
        # Idempotent: revisiting the review screen shouldn't error.
        pass
    else:
        with get_cursor(commit=True) as cur:
            cur.execute(
                "UPDATE healthcare_reviews SET prediction_revealed_at = datetime('now') WHERE screening_id = ?",
                (screening_id,),
            )

    with get_cursor() as cur:
        cur.execute("SELECT * FROM predictions WHERE screening_id = ?", (screening_id,))
        prediction = cur.fetchone()
    if not prediction:
        raise ValidationError("No prediction exists yet for this screening.")

    return dict(prediction)


def submit_review(screening_id: int, reviewed_by: int, data: dict) -> dict:
    require_fields(data, ["notes"])

    review = _get_review_row(screening_id)
    if not review or not review.get("prediction_revealed_at"):
        raise ValidationError(
            "Complete the blinded review (submit your assessment, then reveal the "
            "prediction) before finalizing this review."
        )

    clinician_label = data.get("clinician_label")
    label_source = data.get("label_source")
    if label_source is not None:
        validate_choice(label_source, LABEL_SOURCES, "label_source")

    if label_source == "model_confirmed":
        # "Confirmed" only means the reviewer agreed after seeing the model's
        # output -- it is not independent evidence, so the clinician_label is
        # forced to match the prediction rather than accepting a separately
        # typed value that could quietly diverge from what was actually agreed.
        with get_cursor() as cur:
            cur.execute("SELECT risk_label FROM predictions WHERE screening_id = ?", (screening_id,))
            prediction = cur.fetchone()
        clinician_label = prediction["risk_label"] if prediction else None
        if data.get("agrees_with_model") != 1:
            raise ValidationError("label_source=model_confirmed requires agrees_with_model=1")
    elif clinician_label is not None:
        validate_choice(clinician_label, RISK_LABELS, "clinician_label")
    elif data.get("agrees_with_model") == 0:
        raise ValidationError(
            "clinician_label (with a label_source) is required when disagreeing with the "
            "model, so the true risk category is recorded for future training data."
        )

    with get_cursor(commit=True) as cur:
        cur.execute(
            """UPDATE healthcare_reviews
               SET notes = ?, agrees_with_model = ?, clinician_label = ?, label_source = ?,
                   kl_grade_value = ?, radiograph_ref = ?, acr_criteria_json = ?, reviewed_by = ?
               WHERE screening_id = ?""",
            (
                data["notes"],
                data.get("agrees_with_model"),
                clinician_label,
                label_source,
                data.get("kl_grade_value"),
                data.get("radiograph_ref"),
                data.get("acr_criteria_json"),
                reviewed_by,
                screening_id,
            ),
        )
        cur.execute("UPDATE screenings SET status = 'REVIEWED' WHERE id = ?", (screening_id,))

    return _get_review_row(screening_id)


def get_review(screening_id: int) -> dict:
    return _get_review_row(screening_id)
