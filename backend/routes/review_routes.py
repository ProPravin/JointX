from flask import Blueprint, request, session, jsonify

from backend.services import review_service
from backend.utils.security import login_required, require_role
from backend.utils.validators import require_fields
from backend.utils.helpers import api_success

review_bp = Blueprint("review", __name__, url_prefix="/api/review")


@review_bp.route("", methods=["POST"])
@login_required
@require_role("reviewer", "admin")
def submit_review():
    data = request.get_json(force=True, silent=True) or {}
    require_fields(data, ["screening_id", "notes"])
    result = review_service.submit_review(
        int(data["screening_id"]), session["worker_id"], data
    )
    return jsonify(api_success(result, "Review saved")), 201
