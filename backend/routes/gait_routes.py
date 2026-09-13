from flask import Blueprint, request, jsonify

from backend.services import gait_service
from backend.utils.security import login_required
from backend.utils.validators import require_fields
from backend.utils.helpers import api_success

gait_bp = Blueprint("gait", __name__, url_prefix="/api/gait")


@gait_bp.route("/analyze", methods=["POST"])
@login_required
def analyze_gait():
    data = request.get_json(force=True, silent=True) or {}
    require_fields(data, ["screening_id"])
    result = gait_service.run_gait_test(
        int(data["screening_id"]),
        is_demo=data.get("is_demo"),
        noisy_demo=data.get("noisy_demo", False),
    )
    return jsonify(api_success(result, "Gait analysis complete"))
