"""Generates and persists a SHAP (or heuristic-fallback) explanation for a prediction."""
from database.database import get_cursor
from backend.utils.error_handler import JointXError
from backend.utils.helpers import to_json, from_json
from ml.shap_explainer import explain_prediction


def run_shap_explanation(screening_id: int) -> dict:
    with get_cursor() as cur:
        cur.execute("SELECT * FROM fused_features WHERE screening_id = ?", (screening_id,))
        row = cur.fetchone()
    if not row:
        raise JointXError("Features have not been fused yet", status_code=422)

    fused = from_json(row["feature_json"])
    explanation = explain_prediction(fused["features"])

    with get_cursor(commit=True) as cur:
        cur.execute("DELETE FROM shap_explanations WHERE screening_id = ?", (screening_id,))
        cur.execute(
            """INSERT INTO shap_explanations (screening_id, explanation_json)
               VALUES (?, ?)""",
            (screening_id, to_json(explanation)),
        )

    return explanation


def get_shap_explanation(screening_id: int) -> dict:
    with get_cursor() as cur:
        cur.execute("SELECT * FROM shap_explanations WHERE screening_id = ?", (screening_id,))
        row = cur.fetchone()
    if not row:
        raise JointXError("No SHAP explanation found for this screening", status_code=404)
    return from_json(row["explanation_json"])
