"""
Risk estimation (spec section 10).

If a real trained XGBoost model is present (ml/models/), it is used and
is_prototype=False. Otherwise a transparent, clearly-labelled heuristic
stands in so the demo pipeline still runs end-to-end -- its output is always
tagged is_prototype=True and the UI must show:
"Demo/Prototype Output — Not Clinical Prediction"

The heuristic is NOT a substitute for a validated model and makes no
accuracy claims; it is a simple weighted combination of normalized features
so the rest of the pipeline (SHAP, dashboard, referral) has something
meaningful to explain during development/demos.
"""
import numpy as np

from config.model_config import RISK_THRESHOLDS, RISK_LABELS
from fusion.feature_schema import FEATURE_NAMES
from ml.model_loader import load_model
from backend.utils.logger import get_logger

logger = get_logger(__name__)

# Direction/weight used only by the prototype heuristic: positive weight
# means "higher value -> higher heuristic risk". Roughly informed by general
# OA literature associations, NOT a clinically fitted/validated model.
_HEURISTIC_WEIGHTS = {
    # IMU — higher smoothness/lower jerk-linked values are protective
    "acceleration_rms": 0.05,
    "acceleration_variance": 0.05,
    "peak_acceleration": 0.05,
    "angular_velocity_rms": -0.05,
    "peak_angular_velocity": -0.05,
    "relative_joint_rom": -0.10,
    "movement_smoothness": -0.10,
    "movement_cycle_duration": 0.05,
    # Gait
    "cadence": -0.05,
    "step_time": 0.05,
    "stride_time": 0.05,
    "walking_speed": -0.10,
    "knee_angle_rom": -0.10,
    "stance_swing_ratio": 0.05,
    "left_right_asymmetry": 0.10,
    "gait_cycle_variability": 0.10,
    # Patient
    "age": 0.05,
    "bmi": 0.05,
    "pain_score": 0.20,
    "stiffness_score": 0.15,
    "mobility_score": 0.15,
    # Functional
    "sit_to_stand_time": 0.10,
    "squat_rom": -0.05,
    "balance_stability": 0.10,
    "turn_duration": 0.05,
}

_HEURISTIC_NORM = {
    # name: (typical_min, typical_max) used only to squash into [0,1]
    "acceleration_rms": (0, 2.0),
    "acceleration_variance": (0, 1.0),
    "peak_acceleration": (0, 4.0),
    "angular_velocity_rms": (0, 200),
    "peak_angular_velocity": (0, 400),
    "relative_joint_rom": (0, 90),
    "movement_smoothness": (0, 1),
    "movement_cycle_duration": (0, 2.5),
    "cadence": (60, 130),
    "step_time": (0.3, 1.2),
    "stride_time": (0.6, 2.4),
    "walking_speed": (0, 1.5),
    "knee_angle_rom": (0, 90),
    "stance_swing_ratio": (0.5, 3.0),
    "left_right_asymmetry": (0, 30),
    "gait_cycle_variability": (0, 30),
    "age": (18, 90),
    "bmi": (15, 40),
    "pain_score": (0, 10),
    "stiffness_score": (0, 10),
    "mobility_score": (0, 10),
    "sit_to_stand_time": (2, 20),
    "squat_rom": (0, 90),
    "balance_stability": (0, 1.0),
    "turn_duration": (1, 10),
}


def _normalize(name, value):
    lo, hi = _HEURISTIC_NORM.get(name, (0, 1))
    if hi == lo:
        return 0.0
    return max(0.0, min(1.0, (value - lo) / (hi - lo)))


def _heuristic_score(feature_dict: dict) -> float:
    total_weight = sum(abs(w) for w in _HEURISTIC_WEIGHTS.values())
    score = 0.0
    for name in FEATURE_NAMES:
        value = feature_dict.get(name)
        if value is None:
            continue
        norm = _normalize(name, value)
        weight = _HEURISTIC_WEIGHTS.get(name, 0.0)
        contribution = norm if weight >= 0 else (1 - norm)
        score += abs(weight) * contribution
    return score / total_weight if total_weight else 0.5


def _score_to_label(score: float) -> str:
    if score < RISK_THRESHOLDS["LOW"]:
        return "LOW"
    if score < RISK_THRESHOLDS["MODERATE"]:
        return "MODERATE"
    return "HIGH"


def predict_risk(feature_dict: dict) -> dict:
    """
    Returns:
      {
        "risk_label": "LOW"|"MODERATE"|"HIGH",
        "risk_score": float in [0,1] or None,
        "is_prototype": bool,
        "model_version": str,
      }
    """
    model, is_prototype, version = load_model()

    if model is not None and not is_prototype:
        vector = np.array([[feature_dict.get(n, 0.0) or 0.0 for n in FEATURE_NAMES]])
        try:
            import xgboost as xgb

            dmatrix = xgb.DMatrix(vector, feature_names=FEATURE_NAMES)
            probs = model.predict(dmatrix)[0]  # shape (3,) for LOW/MODERATE/HIGH
            best_idx = int(np.argmax(probs))
            return {
                "risk_label": RISK_LABELS[best_idx],
                "risk_score": float(probs[best_idx]),
                "is_prototype": False,
                "model_version": version,
            }
        except Exception:  # noqa: BLE001
            logger.exception("XGBoost prediction failed, falling back to prototype heuristic")

    score = _heuristic_score(feature_dict)
    return {
        "risk_label": _score_to_label(score),
        "risk_score": round(score, 3),
        "is_prototype": True,
        "model_version": "prototype-heuristic-v1",
    }
