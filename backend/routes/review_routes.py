from flask import Blueprint, request, session, jsonify

from backend.services import review_service, audit_service
from backend.utils.security import login_required, require_role
from backend.utils.validators import require_fields
from backend.utils.helpers import api_success

review_bp = Blueprint("review", __name__, url_prefix="/api/review")


@review_bp.route("/blind", methods=["POST"])
@login_required
@require_role("reviewer", "admin")
def submit_blind():
    """
    Step 1 of the blinded review workflow: the reviewer's own risk-level
    judgement, recorded BEFORE the model's prediction is shown. Must happen
    before /api/review/<id>/reveal or /api/review (spec: Data Integrity #A1).
    """
    data = request.get_json(force=True, silent=True) or {}
    require_fields(data, ["screening_id", "reviewer_label_blind"])
    screening_id = int(data["screening_id"])
    result = review_service.submit_blind_review(screening_id, session["worker_id"], data["reviewer_label_blind"])
    return jsonify(api_success(result, "Blind assessment recorded")), 201


@review_bp.route("/<int:screening_id>/reveal", methods=["POST"])
@login_required
@require_role("reviewer", "admin")
def reveal(screening_id):
    """Step 2: reveal the model's prediction, timestamped. Requires step 1 first."""
    result = review_service.reveal_prediction(screening_id)
    audit_service.log_action(session["worker_id"], "PREDICTION_REVEALED", "screening", screening_id)
    return jsonify(api_success(result))


@review_bp.route("", methods=["POST"])
@login_required
@require_role("reviewer", "admin")
def submit_review():
    """Step 3: finalize the review. Requires steps 1 and 2 to have happened."""
    data = request.get_json(force=True, silent=True) or {}
    require_fields(data, ["screening_id", "notes"])
    screening_id = int(data["screening_id"])
    result = review_service.submit_review(screening_id, session["worker_id"], data)
    audit_service.log_action(session["worker_id"], "REVIEW_SUBMITTED", "screening", screening_id, {"label_source": data.get("label_source")})
    return jsonify(api_success(result, "Review saved")), 201
