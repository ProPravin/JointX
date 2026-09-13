"""Runs risk prediction on a screening's fused feature vector and persists it."""
from database.database import get_cursor
from backend.utils.error_handler import JointXError
from backend.utils.helpers import from_json
from ml.predictor import predict_risk


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
    result = predict_risk(fused["features"])

    with get_cursor(commit=True) as cur:
        cur.execute("DELETE FROM predictions WHERE screening_id = ?", (screening_id,))
        cur.execute(
            """INSERT INTO predictions
               (screening_id, risk_label, risk_score, model_version, is_prototype)
               VALUES (?, ?, ?, ?, ?)""",
            (
                screening_id,
                result["risk_label"],
                result["risk_score"],
                result["model_version"],
                int(result["is_prototype"]),
            ),
        )
        cur.execute("UPDATE screenings SET status = 'PREDICTED' WHERE id = ?", (screening_id,))

    return result


def get_prediction(screening_id: int) -> dict:
    with get_cursor() as cur:
        cur.execute("SELECT * FROM predictions WHERE screening_id = ?", (screening_id,))
        row = cur.fetchone()
    if not row:
        raise JointXError("No prediction found for this screening", status_code=404)
    return dict(row)
