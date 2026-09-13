"""Runs risk prediction on a screening's fused feature vector and persists it."""
from database.database import get_cursor
from backend.utils.error_handler import JointXError
from backend.utils.helpers import from_json
from ml.predictor import predict_risk
from config.model_config import MIN_FEATURE_BLOCKS_PRESENT, MIN_OVERALL_CAPTURE_QUALITY


def _refusal_check(features: dict) -> str:
    """
    Returns a human-readable refusal reason if the captured data is
    insufficient to predict on, or None if prediction should proceed
    (spec: Data Integrity #A2 REFUSAL GATE).
    """
    blocks = {
        "questionnaire": (bool(features.get("questionnaire_complete")), 1.0),
        "gait": (bool(features.get("gait_present")), features.get("gait_quality") or 0.0),
        "imu": (bool(features.get("imu_present")), features.get("imu_quality") or 0.0),
        "functional": (bool(features.get("functional_present")), features.get("functional_quality") or 0.0),
    }
    present = [name for name, (is_present, _q) in blocks.items() if is_present]
    if len(present) < MIN_FEATURE_BLOCKS_PRESENT:
        missing = [name for name in blocks if name not in present]
        return (
            f"Only {len(present)} of 4 feature blocks captured (missing: {', '.join(missing)}); "
            f"at least {MIN_FEATURE_BLOCKS_PRESENT} are required."
        )

    avg_quality = sum(blocks[name][1] for name in present) / len(present)
    if avg_quality < MIN_OVERALL_CAPTURE_QUALITY:
        return (
            f"Overall capture quality ({avg_quality:.2f}) is below the minimum required "
            f"({MIN_OVERALL_CAPTURE_QUALITY}) across the captured blocks ({', '.join(present)})."
        )
    return None


def run_prediction(screening_id: int) -> dict:
    with get_cursor() as cur:
        cur.execute("SELECT * FROM fused_features WHERE screening_id = ?", (screening_id,))
        row = cur.fetchone()
    if not row:
        raise JointXError(
            "Features have not been fused yet — run feature fusion before prediction",
            status_code=422,
        )

    fused = from_json(row["feature_json"])
    features = fused["features"]

    refusal_reason = _refusal_check(features)

    if refusal_reason:
        result = {
            "risk_label": "REFUSED",
            "risk_score": None,
            "model_version": None,
            "is_prototype": True,
            "refused": True,
            "refusal_reason": refusal_reason,
        }
        new_status = "REFUSED"
    else:
        result = predict_risk(features)
        result["refused"] = False
        result["refusal_reason"] = None
        new_status = "PREDICTED"

    with get_cursor(commit=True) as cur:
        cur.execute("DELETE FROM predictions WHERE screening_id = ?", (screening_id,))
        cur.execute(
            """INSERT INTO predictions
               (screening_id, risk_label, risk_score, model_version, is_prototype, refused, refusal_reason)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                screening_id,
                result["risk_label"],
                result["risk_score"],
                result["model_version"],
                int(result["is_prototype"]),
                int(result["refused"]),
                result["refusal_reason"],
            ),
        )
        cur.execute("UPDATE screenings SET status = ? WHERE id = ?", (new_status, screening_id))

    return result


def get_prediction(screening_id: int) -> dict:
    with get_cursor() as cur:
        cur.execute("SELECT * FROM predictions WHERE screening_id = ?", (screening_id,))
        row = cur.fetchone()
    if not row:
        raise JointXError("No prediction found for this screening", status_code=404)
    return dict(row)
