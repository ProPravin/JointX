from flask import Blueprint, request, session, jsonify

from backend.services import patient_service
from backend.utils.security import login_required, require_role
from backend.utils.helpers import api_success
from config.roles import tier_for_role

patient_bp = Blueprint("patients", __name__, url_prefix="/api/patients")


@patient_bp.route("", methods=["POST"])
@login_required
@require_role("worker", "admin")
def create_patient():
    data = request.get_json(force=True, silent=True) or {}
    patient = patient_service.create_patient(data, session["worker_id"])
    return jsonify(api_success(patient, "Patient registered successfully")), 201


@patient_bp.route("", methods=["GET"])
@login_required
def list_patients():
    query = request.args.get("q", "")
    # Healthcare Workers only see patients registered at their own facility;
    # Doctors/Reviewers and Admins see across facilities (clinical oversight).
    facility_name = None
    if tier_for_role(session.get("worker_role")) == "worker":
        from database.database import get_cursor

        with get_cursor() as cur:
            cur.execute("SELECT facility_name FROM healthcare_workers WHERE id = ?", (session["worker_id"],))
            row = cur.fetchone()
        facility_name = row["facility_name"] if row else None

    patients = patient_service.search_patients(query, facility_name=facility_name)
    return jsonify(api_success(patients))


@patient_bp.route("/<int:patient_id>", methods=["GET"])
@login_required
def get_patient(patient_id):
    patient = patient_service.get_patient(patient_id)
    patient["screening_history"] = patient_service.get_patient_screening_history(patient_id)
    return jsonify(api_success(patient))


@patient_bp.route("/<int:patient_id>/risk-history", methods=["GET"])
@login_required
def get_patient_risk_history(patient_id):
    history = patient_service.get_patient_risk_history(patient_id)
    return jsonify(api_success(history))
