from flask import Blueprint, request, jsonify

from backend.services import functional_service
from backend.utils.security import login_required
from backend.utils.validators import require_fields
from backend.utils.helpers import api_success

functional_bp = Blueprint("functional", __name__, url_prefix="/api/functional")


@functional_bp.route("/sit-to-stand", methods=["POST"])
@login_required
def sit_to_stand():
    data = request.get_json(force=True, silent=True) or {}
    require_fields(data, ["screening_id"])
    result = functional_service.run_sit_to_stand_test(int(data["screening_id"]))
    return jsonify(api_success(result, "Sit-to-stand test complete"))


@functional_bp.route("/squat", methods=["POST"])
@login_required
def squat():
    data = request.get_json(force=True, silent=True) or {}
    require_fields(data, ["screening_id"])
    result = functional_service.run_squat_test(int(data["screening_id"]), is_demo=data.get("is_demo"))
    return jsonify(api_success(result, "Squat test complete"))


@functional_bp.route("/balance", methods=["POST"])
@login_required
def balance():
    data = request.get_json(force=True, silent=True) or {}
    require_fields(data, ["screening_id"])
    result = functional_service.run_balance_test(int(data["screening_id"]))
    return jsonify(api_success(result, "Balance test complete"))


@functional_bp.route("/turn", methods=["POST"])
@login_required
def turn():
    data = request.get_json(force=True, silent=True) or {}
    require_fields(data, ["screening_id"])
    result = functional_service.run_turn_test(int(data["screening_id"]))
    return jsonify(api_success(result, "Turn test complete"))
