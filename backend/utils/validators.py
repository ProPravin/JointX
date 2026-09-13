"""
Input validation for API payloads. Raises ValidationError (caught centrally
by backend/utils/error_handler.py) rather than letting bad input propagate
into the database or ML pipeline.
"""


class ValidationError(Exception):
    def __init__(self, message):
        super().__init__(message)
        self.message = message


def require_fields(data: dict, fields: list):
    if not isinstance(data, dict):
        raise ValidationError("Request body must be a JSON object")
    missing = [f for f in fields if data.get(f) in (None, "")]
    if missing:
        raise ValidationError(f"Missing required field(s): {', '.join(missing)}")


def validate_range(value, min_value, max_value, field_name):
    if value is None:
        return
    try:
        v = float(value)
    except (TypeError, ValueError):
        raise ValidationError(f"{field_name} must be numeric")
    if not (min_value <= v <= max_value):
        raise ValidationError(f"{field_name} must be between {min_value} and {max_value}")


def validate_sex(value):
    if value not in ("M", "F", "OTHER", None):
        raise ValidationError("sex must be one of M, F, OTHER")


def validate_choice(value, choices, field_name):
    if value not in choices:
        raise ValidationError(f"{field_name} must be one of {choices}")
