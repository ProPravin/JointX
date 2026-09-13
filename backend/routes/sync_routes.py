from flask import Blueprint, jsonify

from backend.services import sync_service
from backend.utils.security import login_required
from backend.utils.helpers import api_success

sync_bp = Blueprint("sync", __name__, url_prefix="/api/sync")


@sync_bp.route("", methods=["POST"])
@login_required
def trigger_sync():
    result = sync_service.run_sync()
    return jsonify(api_success(result, "Sync attempted"))


@sync_bp.route("/status", methods=["GET"])
@login_required
def sync_status():
    result = sync_service.get_sync_summary()
    return jsonify(api_success(result))
