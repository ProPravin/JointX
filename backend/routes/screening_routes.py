from flask import Blueprint, request, session, jsonify

from backend.services import screening_service
from backend.utils.security import login_required, require_role
from backend.utils.validators import require_fields
from backend.utils.helpers import api_success
from config.settings import Config

screening_bp = Blueprint("screenings", __name__, url_prefix="/api/screenings")


@screening_bp.route("", methods=["POST"])
@login_required
@require_role("worker", "admin")
def start_screening():
    data = request.get_json(force=True, silent=True) or {}
    require_fields(data, ["patient_id"])
    is_demo = data.get("is_demo", Config.DEMO_MODE)
    screening = screening_service.start_screening(
        int(data["patient_id"]), session["worker_id"], is_demo=is_demo
    )
    return jsonify(api_success(screening, "Screening started")), 201


@screening_bp.route("/<int:screening_id>", methods=["GET"])
@login_required
def get_screening(screening_id):
    record = screening_service.get_full_screening_record(screening_id)
    return jsonify(api_success(record))


@screening_bp.route("/dashboard/summary", methods=["GET"])
@login_required
def dashboard_summary():
    """Aggregate stats for the healthcare-worker dashboard (spec section 13)."""
    from database.database import get_cursor

    with get_cursor() as cur:
        cur.execute("SELECT COUNT(*) c FROM patients")
        total_patients = cur.fetchone()["c"]

        cur.execute("SELECT COUNT(*) c FROM screenings")
        total_screenings = cur.fetchone()["c"]

        cur.execute(
            """SELECT s.id, s.started_at, p.full_name, p.patient_code, pr.risk_label
               FROM screenings s
               JOIN patients p ON p.id = s.patient_id
               LEFT JOIN predictions pr ON pr.screening_id = s.id
               ORDER BY s.started_at DESC LIMIT 10"""
        )
        recent_screenings = [dict(r) for r in cur.fetchall()]

        cur.execute(
            """SELECT risk_label, COUNT(*) c FROM predictions GROUP BY risk_label"""
        )
        risk_distribution = {r["risk_label"]: r["c"] for r in cur.fetchall()}

        cur.execute(
            "SELECT COUNT(*) c FROM referrals WHERE status IN ('REFERRAL_CREATED','PENDING')"
        )
        pending_referrals = cur.fetchone()["c"]

        cur.execute(
            "SELECT COUNT(*) c FROM referrals WHERE status = 'FOLLOW_UP_REQUIRED'"
        )
        follow_up_cases = cur.fetchone()["c"]

        cur.execute("SELECT COUNT(*) c FROM sync_queue WHERE status = 'PENDING'")
        unsynced = cur.fetchone()["c"]

        cur.execute("SELECT MAX(synced_at) t FROM sync_queue WHERE status = 'SYNCED'")
        last_sync = cur.fetchone()["t"]

    summary = {
        "total_patients": total_patients,
        "total_screenings": total_screenings,
        "recent_screenings": recent_screenings,
        "risk_distribution": risk_distribution,
        "pending_referrals": pending_referrals,
        "follow_up_cases": follow_up_cases,
        "unsynced_records": unsynced,
        "last_synchronization": last_sync,
    }
    return jsonify(api_success(summary))
