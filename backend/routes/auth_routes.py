from flask import Blueprint, request, session, jsonify

from database.database import get_cursor
from backend.utils.security import verify_password
from backend.utils.validators import require_fields
from backend.utils.helpers import api_success, api_error
from config.roles import tier_for_role, label_for_role

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")


@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json(force=True, silent=True) or {}
    require_fields(data, ["username", "password"])

    with get_cursor() as cur:
        cur.execute(
            "SELECT * FROM healthcare_workers WHERE username = ? AND is_active = 1",
            (data["username"],),
        )
        worker = cur.fetchone()

    if not worker or not verify_password(data["password"], worker["password_hash"]):
        return jsonify(api_error("Invalid username or password")), 401

    session["worker_id"] = worker["id"]
    session["worker_name"] = worker["full_name"]
    session["worker_role"] = worker["role"]
    session["worker_language"] = worker.get("language") or "en"

    return jsonify(
        api_success(
            {
                "id": worker["id"],
                "full_name": worker["full_name"],
                "role": worker["role"],
                "role_tier": tier_for_role(worker["role"]),
                "role_label": label_for_role(worker["role"]),
                "facility_name": worker["facility_name"],
                "language": session["worker_language"],
            },
            "Login successful",
        )
    )


@auth_bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify(api_success(message="Logged out"))


@auth_bp.route("/me", methods=["GET"])
def me():
    if not session.get("worker_id"):
        return jsonify(api_error("Not authenticated")), 401
    return jsonify(
        api_success(
            {
                "id": session["worker_id"],
                "full_name": session.get("worker_name"),
                "role": session.get("worker_role"),
                "role_tier": tier_for_role(session.get("worker_role")),
                "role_label": label_for_role(session.get("worker_role")),
                "language": session.get("worker_language", "en"),
            }
        )
    )
