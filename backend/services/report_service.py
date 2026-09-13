"""Builds the structured data used by the report screen/PDF (spec section 25)."""
from config.settings import Config
from backend.services.screening_service import get_full_screening_record


def build_report(screening_id: int) -> dict:
    record = get_full_screening_record(screening_id)
    record["disclaimer"] = Config.DISCLAIMER_GENERAL

    prediction = record.get("prediction")
    if prediction and prediction.get("risk_label") in ("MODERATE", "HIGH"):
        record["further_evaluation_notice"] = Config.DISCLAIMER_FURTHER_EVAL
    else:
        record["further_evaluation_notice"] = None

    if record["screening"].get("is_demo") or (
        record.get("gait_features") and record["gait_features"].get("is_demo")
    ):
        record["demo_data_notice"] = Config.DISCLAIMER_DEMO_DATA
    else:
        record["demo_data_notice"] = None

    if prediction and prediction.get("is_prototype"):
        record["prototype_notice"] = Config.DISCLAIMER_PROTOTYPE_MODEL
    else:
        record["prototype_notice"] = None

    return record
