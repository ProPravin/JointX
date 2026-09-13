"""
Admin-only worker management + audit log viewing (spec: Production-grade
RBAC #1/#3/#5). Every route here is @require_role("admin").
"""
from flask import Blueprint, request, session, jsonify

from backend.utils.security import login_required, require_role
from backend.utils.validators import require_fields
from backend.utils.helpers import api_success
from backend.services import admin_service, audit_service

admin_bp = Blueprint("admin", __name__, url_prefix="/api/admin")


@admin_bp.route("/workers", methods=["GET"])
@login_required
@require_role("admin")
def list_workers():
    return jsonify(api_success(admin_service.list_workers()))


@admin_bp.route("/workers", methods=["POST"])
@login_required
@require_role("admin")
def create_worker():
    data = request.get_json(force=True, silent=True) or {}
    require_fields(data, ["username", "password", "full_name", "role"])

    worker = admin_service.create_worker(
        username=data["username"],
        password=data["password"],
        full_name=data["full_name"],
        role=data["role"],
        facility_name=data.get("facility_name"),
        created_by=session["worker_id"],
    )
    audit_service.log_action(session["worker_id"], "WORKER_CREATED", "healthcare_worker", worker["id"], {"role": worker["role"]})
    return jsonify(api_success(worker, "Worker created")), 201


@admin_bp.route("/workers/<int:worker_id>/active", methods=["PUT"])
@login_required
@require_role("admin")
def set_worker_active(worker_id):
    data = request.get_json(force=True, silent=True) or {}
    require_fields(data, ["is_active"])

    worker = admin_service.set_worker_active(worker_id, bool(data["is_active"]))
    action = "WORKER_ENABLED" if data["is_active"] else "WORKER_DISABLED"
    audit_service.log_action(session["worker_id"], action, "healthcare_worker", worker_id)
    return jsonify(api_success(worker, "Worker updated"))


@admin_bp.route("/workers/<int:worker_id>/reset-password", methods=["POST"])
@login_required
@require_role("admin")
def reset_worker_password(worker_id):
    data = request.get_json(force=True, silent=True) or {}
    require_fields(data, ["new_password"])

    worker = admin_service.reset_worker_password(worker_id, data["new_password"])
    audit_service.log_action(session["worker_id"], "PASSWORD_RESET", "healthcare_worker", worker_id)
    return jsonify(api_success(worker, "Password reset"))


@admin_bp.route("/audit-log", methods=["GET"])
@login_required
@require_role("admin")
def audit_log():
    action = request.args.get("action")
    limit = int(request.args.get("limit", 200))
    return jsonify(api_success(audit_service.list_audit_log(limit=limit, action=action)))
