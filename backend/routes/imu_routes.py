from flask import Blueprint, request, jsonify

from backend.services import imu_service
from backend.utils.security import login_required
from backend.utils.validators import require_fields
from backend.utils.helpers import api_success

imu_bp = Blueprint("imu", __name__, url_prefix="/api/imu")


@imu_bp.route("/calibrate", methods=["POST"])
@login_required
def calibrate():
    result = imu_service.calibrate_imu()
    return jsonify(api_success(result, "IMU calibration complete"))


@imu_bp.route("/start", methods=["POST"])
@login_required
def start():
    result = imu_service.start_imu()
    return jsonify(api_success(result, "IMU capture started"))


@imu_bp.route("/stop", methods=["POST"])
@login_required
def stop():
    result = imu_service.stop_imu()
    return jsonify(api_success(result, "IMU capture stopped"))


@imu_bp.route("/analyze", methods=["POST"])
@login_required
def analyze():
    data = request.get_json(force=True, silent=True) or {}
    require_fields(data, ["screening_id"])
    result = imu_service.run_imu_movement_test(int(data["screening_id"]))
    return jsonify(api_success(result, "IMU analysis complete"))
