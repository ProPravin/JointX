"""Small shared helper functions used across services."""
import json
import uuid
from datetime import datetime


def generate_patient_code(prefix="JX"):
    return f"{prefix}-{datetime.now().strftime('%y%m%d')}-{uuid.uuid4().hex[:6].upper()}"


def to_json(obj) -> str:
    return json.dumps(obj, default=str)


def from_json(text, default=None):
    if not text:
        return default
    try:
        return json.loads(text)
    except (TypeError, ValueError):
        return default


def api_success(data=None, message="Operation completed successfully"):
    return {"success": True, "data": data if data is not None else {}, "message": message}


def api_error(message):
    return {"success": False, "error": message}


def compute_bmi(height_cm, weight_kg):
    if not height_cm or not weight_kg:
        return None
    h_m = height_cm / 100.0
    if h_m <= 0:
        return None
    return round(weight_kg / (h_m ** 2), 2)
