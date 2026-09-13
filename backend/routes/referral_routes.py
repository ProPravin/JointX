from flask import Blueprint, request, session, jsonify

from backend.services import referral_service
from backend.utils.security import login_required
from backend.utils.validators import require_fields
from backend.utils.helpers import api_success

referral_bp = Blueprint("referrals", __name__, url_prefix="/api/referrals")


@referral_bp.route("", methods=["POST"])
@login_required
def create_referral():
    data = request.get_json(force=True, silent=True) or {}
    require_fields(data, ["screening_id"])
    result = referral_service.create_referral(
        int(data["screening_id"]), session["worker_id"], data
    )
    return jsonify(api_success(result, "Referral created")), 201


@referral_bp.route("", methods=["GET"])
@login_required
def list_referrals():
    status = request.args.get("status")
    results = referral_service.list_referrals(status)
    return jsonify(api_success(results))


@referral_bp.route("/<int:referral_id>", methods=["PUT"])
@login_required
def update_referral(referral_id):
    data = request.get_json(force=True, silent=True) or {}
    result = referral_service.update_referral(referral_id, data)
    return jsonify(api_success(result, "Referral updated"))
