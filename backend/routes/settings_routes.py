"""Per-worker UI preferences (currently just language)."""
from flask import Blueprint, request, session, jsonify

from database.database import get_cursor
from backend.utils.security import login_required
from backend.utils.validators import require_fields, validate_choice
from backend.utils.helpers import api_success
from config.i18n import SUPPORTED_LANGUAGES

settings_bp = Blueprint("settings", __name__, url_prefix="/api/settings")


@settings_bp.route("/language", methods=["POST"])
@login_required
def set_language():
    data = request.get_json(force=True, silent=True) or {}
    require_fields(data, ["language"])
    validate_choice(data["language"], list(SUPPORTED_LANGUAGES.keys()), "language")

    with get_cursor(commit=True) as cur:
        cur.execute(
            "UPDATE healthcare_workers SET language = ? WHERE id = ?",
            (data["language"], session["worker_id"]),
        )

    session["worker_language"] = data["language"]
    return jsonify(api_success({"language": data["language"]}, "Language preference saved"))
