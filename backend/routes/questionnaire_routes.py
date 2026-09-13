from flask import Blueprint, request, jsonify

from backend.services import questionnaire_service, screening_service
from backend.utils.security import login_required
from backend.utils.validators import require_fields
from backend.utils.helpers import api_success

questionnaire_bp = Blueprint("questionnaire", __name__, url_prefix="/api/questionnaire")


@questionnaire_bp.route("", methods=["POST"])
@login_required
def submit_questionnaire():
    data = request.get_json(force=True, silent=True) or {}
    require_fields(data, ["screening_id"])
    screening_id = int(data["screening_id"])

    result = questionnaire_service.submit_questionnaire(screening_id, data)
    screening_service.update_screening_status(screening_id, "DATA_COLLECTED")
    return jsonify(api_success(result, "Questionnaire saved")), 201
