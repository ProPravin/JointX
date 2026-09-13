"""
SHAP explanation (spec section 11).

When a real trained XGBoost model is loaded, this uses the `shap` library
for true Shapley-value feature attributions. In prototype/demo mode (no
trained model), it falls back to reporting each feature's weighted,
normalized contribution to the heuristic score from ml/predictor.py — this
is clearly labelled as a heuristic breakdown, NOT SHAP, so the UI never
implies a real model explanation exists when it doesn't.

SHAP explains model behaviour; it does not establish medical causation.
"""
from config.model_config import SHAP_TOP_N_FEATURES
from fusion.feature_schema import FEATURE_NAMES
from ml.model_loader import load_model
from ml.predictor import _HEURISTIC_WEIGHTS, _HEURISTIC_NORM, _normalize
from backend.utils.logger import get_logger

logger = get_logger(__name__)

try:
    import shap
    import numpy as np

    SHAP_AVAILABLE = True
except ImportError:  # pragma: no cover
    SHAP_AVAILABLE = False
    logger.warning("shap not installed — using heuristic contribution fallback")


def _heuristic_contributions(feature_dict: dict) -> list:
    total_weight = sum(abs(w) for w in _HEURISTIC_WEIGHTS.values()) or 1.0
    contributions = []
    for name in FEATURE_NAMES:
        value = feature_dict.get(name)
        weight = _HEURISTIC_WEIGHTS.get(name, 0.0)
        if value is None:
            continue
        norm = _normalize(name, value)
        signed_contribution = weight * norm / total_weight
        contributions.append(
            {
                "feature": name,
                "value": value,
                "contribution": round(signed_contribution, 4),
                "direction": "increases_risk" if signed_contribution > 0 else "decreases_risk",
                "method": "heuristic_weight (prototype — not SHAP)",
            }
        )
    contributions.sort(key=lambda c: abs(c["contribution"]), reverse=True)
    return contributions[:SHAP_TOP_N_FEATURES]


def explain_prediction(feature_dict: dict) -> dict:
    model, is_prototype, version = load_model()

    if SHAP_AVAILABLE and model is not None and not is_prototype:
        try:
            explainer = shap.TreeExplainer(model)
            vector = np.array([[feature_dict.get(n, 0.0) or 0.0 for n in FEATURE_NAMES]])
            shap_values = explainer.shap_values(vector)
            # multi-class: shap_values is a list per class; explain the
            # predicted class only, chosen by caller if needed — default to
            # the class with the largest |contribution| sum here.
            if isinstance(shap_values, list):
                sums = [abs(sv[0]).sum() for sv in shap_values]
                class_values = shap_values[sums.index(max(sums))][0]
            else:
                class_values = shap_values[0]

            contributions = []
            for name, val, feat_val in zip(FEATURE_NAMES, class_values, vector[0]):
                contributions.append(
                    {
                        "feature": name,
                        "value": float(feat_val),
                        "contribution": round(float(val), 4),
                        "direction": "increases_risk" if val > 0 else "decreases_risk",
                        "method": "shap_tree_explainer",
                    }
                )
            contributions.sort(key=lambda c: abs(c["contribution"]), reverse=True)
            return {"method": "shap", "top_features": contributions[:SHAP_TOP_N_FEATURES]}
        except Exception:  # noqa: BLE001
            logger.exception("SHAP explanation failed, falling back to heuristic")

    return {"method": "heuristic", "top_features": _heuristic_contributions(feature_dict)}
