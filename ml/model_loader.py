"""
Loads a trained XGBoost model from disk if one exists. If not, the app
enters UNVALIDATED PROTOTYPE MODE (spec section 10) rather than fabricating
a model or claiming clinical validity.
"""
import os

from config.settings import Config
from backend.utils.logger import get_logger

logger = get_logger(__name__)

try:
    import xgboost as xgb

    XGBOOST_AVAILABLE = True
except ImportError:  # pragma: no cover
    XGBOOST_AVAILABLE = False
    logger.warning("xgboost not installed — running in prototype-only mode")

_cached_model = None
_cached_model_version = None


def model_exists() -> bool:
    return XGBOOST_AVAILABLE and os.path.exists(Config.MODEL_PATH)


def load_model():
    """
    Returns (model_or_None, is_prototype: bool, version: str).
    A None model means the caller must use the rule-based prototype
    estimator in ml/predictor.py instead of XGBoost.
    """
    global _cached_model, _cached_model_version

    if not model_exists():
        return None, True, "prototype-heuristic-v1"

    if _cached_model is not None:
        return _cached_model, False, _cached_model_version

    try:
        booster = xgb.Booster()
        booster.load_model(Config.MODEL_PATH)
        _cached_model = booster
        _cached_model_version = os.path.basename(Config.MODEL_PATH)
        logger.info("Loaded trained XGBoost model: %s", _cached_model_version)
        return _cached_model, False, _cached_model_version
    except Exception as e:  # noqa: BLE001 - must never crash the app on load failure
        logger.exception("Failed to load XGBoost model: %s", e)
        return None, True, "prototype-heuristic-v1"
