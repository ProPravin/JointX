from flask import Blueprint, jsonify

from backend.services import imu_service
from backend.utils.security import login_required
from backend.utils.helpers import api_success
from database.database import get_cursor
from config.settings import Config

device_bp = Blueprint("device", __name__, url_prefix="/api/device-status")


@device_bp.route("", methods=["GET"])
@login_required
def device_status():
    imu_status = imu_service.get_device_status()

    camera_status = "SIMULATED" if Config.DEMO_MODE else "UNKNOWN"
    if not Config.DEMO_MODE:
        try:
            from computer_vision.pose_detection import CV_AVAILABLE

            camera_status = "AVAILABLE" if CV_AVAILABLE else "UNAVAILABLE"
        except Exception:  # noqa: BLE001
            camera_status = "UNAVAILABLE"

    with get_cursor() as cur:
        cur.execute("SELECT COUNT(*) c FROM sync_queue WHERE status = 'PENDING'")
        unsynced = cur.fetchone()["c"]

    status = {
        "camera": camera_status,
        "imu_left": imu_status.get("left"),
        "imu_right": imu_status.get("right"),
        "imu_is_demo": imu_status.get("is_demo"),
        "demo_mode": Config.DEMO_MODE,
        "unsynced_records": unsynced,
    }
    return jsonify(api_success(status))
