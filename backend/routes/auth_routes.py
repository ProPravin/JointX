from datetime import datetime, timedelta

from flask import Blueprint, request, session, jsonify

from database.database import get_cursor
from backend.utils.security import verify_password, hash_password, validate_password_strength
from backend.utils.validators import require_fields, ValidationError
from backend.utils.helpers import api_success, api_error
from backend.services import audit_service
from config.roles import tier_for_role, label_for_role, tier_for_display_role, DISPLAY_ROLES
from config.settings import Config

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

    if worker and worker.get("locked_until"):
        locked_until = datetime.fromisoformat(worker["locked_until"])
        if datetime.now() < locked_until:
            audit_service.log_action(worker["id"], "LOGIN_BLOCKED_LOCKED", "healthcare_worker", worker["id"])
            return jsonify(api_error(
                f"Account locked due to repeated failed logins. Try again after {locked_until.strftime('%H:%M:%S')}."
            )), 423

    if not worker or not verify_password(data["password"], worker["password_hash"]):
        if worker:
            _record_failed_login(worker)
        audit_service.log_action(worker["id"] if worker else None, "LOGIN_FAILED", "healthcare_worker", worker["id"] if worker else None, {"username": data["username"]})
        return jsonify(api_error("Invalid username or password")), 401

    # Real-time, DB-backed role check: the role picked in the login dropdown
    # must match this account's actual stored role tier. This is what makes
    # the Role selector meaningful rather than cosmetic — picking the wrong
    # portal for a real account is rejected here, not silently allowed.
    selected_role = data.get("role")
    if selected_role:
        expected_tier = tier_for_display_role(selected_role)
        if not expected_tier:
            return jsonify(api_error(f"role must be one of {list(DISPLAY_ROLES)}")), 400
        if tier_for_role(worker["role"]) != expected_tier:
            audit_service.log_action(worker["id"], "LOGIN_FAILED_WRONG_ROLE", "healthcare_worker", worker["id"], {"selected_role": selected_role})
            return (
                jsonify(api_error(f"This account is not registered as {selected_role}. Please select the correct role.")),
                403,
            )

    _clear_failed_logins(worker["id"])

    session["worker_id"] = worker["id"]
    session["worker_name"] = worker["full_name"]
    session["worker_role"] = worker["role"]
    session["worker_language"] = worker.get("language") or "en"

    audit_service.log_action(worker["id"], "LOGIN_SUCCESS", "healthcare_worker", worker["id"])

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


def _record_failed_login(worker: dict):
    attempts = (worker.get("failed_login_attempts") or 0) + 1
    locked_until = None
    if attempts >= Config.MAX_FAILED_LOGIN_ATTEMPTS:
        locked_until = (datetime.now() + timedelta(minutes=Config.LOCKOUT_MINUTES)).isoformat()
    with get_cursor(commit=True) as cur:
        cur.execute(
            "UPDATE healthcare_workers SET failed_login_attempts = ?, locked_until = ? WHERE id = ?",
            (attempts, locked_until, worker["id"]),
        )


def _clear_failed_logins(worker_id: int):
    with get_cursor(commit=True) as cur:
        cur.execute(
            "UPDATE healthcare_workers SET failed_login_attempts = 0, locked_until = NULL WHERE id = ?",
            (worker_id,),
        )


@auth_bp.route("/register", methods=["POST"])
def register():
    """
    Self-service account creation for any of the three portal roles.
    Available ONLY in demo mode (JOINTX_DEMO_MODE=true) — a real deployment
    must provision accounts through an Admin (see backend/routes/admin_routes.py
    and the "flask create-admin" CLI command for the very first Admin
    account), never through an unauthenticated public endpoint. See README.md.
    """
    if not Config.DEMO_MODE:
        return jsonify(api_error("Self-registration is disabled outside demo mode. Ask an administrator to create your account.")), 404

    data = request.get_json(force=True, silent=True) or {}
    require_fields(data, ["username", "password", "full_name", "role"])

    role_display = data["role"]
    db_role = DISPLAY_ROLES.get(role_display)
    if not db_role:
        raise ValidationError(f"role must be one of {list(DISPLAY_ROLES)}")

    validate_password_strength(data["password"])

    with get_cursor() as cur:
        cur.execute("SELECT id FROM healthcare_workers WHERE username = ?", (data["username"],))
        if cur.fetchone():
            raise ValidationError("That username is already taken")

    with get_cursor(commit=True) as cur:
        cur.execute(
            """INSERT INTO healthcare_workers (username, password_hash, full_name, role, facility_name)
               VALUES (?, ?, ?, ?, ?)""",
            (
                data["username"],
                hash_password(data["password"]),
                data["full_name"],
                db_role,
                data.get("facility_name"),
            ),
        )
        worker_id = cur.lastrowid

    audit_service.log_action(worker_id, "WORKER_SELF_REGISTERED", "healthcare_worker", worker_id, {"role": db_role})

    session["worker_id"] = worker_id
    session["worker_name"] = data["full_name"]
    session["worker_role"] = db_role
    session["worker_language"] = "en"

    return (
        jsonify(
            api_success(
                {
                    "id": worker_id,
                    "full_name": data["full_name"],
                    "role": db_role,
                    "role_tier": tier_for_role(db_role),
                    "role_label": label_for_role(db_role),
                    "language": "en",
                },
                "Registration successful",
            )
        ),
        201,
    )


@auth_bp.route("/logout", methods=["POST"])
def logout():
    worker_id = session.get("worker_id")
    if worker_id:
        audit_service.log_action(worker_id, "LOGOUT", "healthcare_worker", worker_id)
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
