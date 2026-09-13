"""
Centralized error handling so no single failing sensor/service/route can
crash the whole application (see spec section 20).
"""
import sqlite3

from flask import jsonify

from backend.utils.validators import ValidationError
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class JointXError(Exception):
    """Base class for expected, user-facing application errors."""

    def __init__(self, message, status_code=400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class DeviceUnavailableError(JointXError):
    def __init__(self, message="Device unavailable"):
        super().__init__(message, status_code=503)


class DataQualityError(JointXError):
    def __init__(self, message="Insufficient data quality"):
        super().__init__(message, status_code=422)


class ModelUnavailableError(JointXError):
    def __init__(self, message="AI model unavailable — screening cannot produce a validated prediction."):
        super().__init__(message, status_code=503)


def register_error_handlers(app):
    @app.errorhandler(ValidationError)
    def handle_validation(e):
        return jsonify({"success": False, "error": e.message}), 400

    @app.errorhandler(JointXError)
    def handle_jointx_error(e):
        logger.warning("JointXError: %s", e.message)
        return jsonify({"success": False, "error": e.message}), e.status_code

    @app.errorhandler(sqlite3.Error)
    def handle_db_error(e):
        logger.exception("Database error")
        return jsonify({"success": False, "error": "A database error occurred"}), 500

    @app.errorhandler(404)
    def handle_404(e):
        return jsonify({"success": False, "error": "Resource not found"}), 404

    @app.errorhandler(500)
    def handle_500(e):
        logger.exception("Unhandled server error")
        return jsonify({"success": False, "error": "An unexpected error occurred"}), 500
