from flask import Blueprint, request, session, jsonify

from backend.services import patient_service
from backend.utils.security import login_required
from backend.utils.helpers import api_success

patient_bp = Blueprint("patients", __name__, url_prefix="/api/patients")


@patient_bp.route("", methods=["POST"])
@login_required
def create_patient():
    data = request.get_json(force=True, silent=True) or {}
    patient = patient_service.create_patient(data, session["worker_id"])
    return jsonify(api_success(patient, "Patient registered successfully")), 201


@patient_bp.route("", methods=["GET"])
@login_required
def list_patients():
    query = request.args.get("q", "")
    patients = patient_service.search_patients(query)
    return jsonify(api_success(patients))


@patient_bp.route("/<int:patient_id>", methods=["GET"])
@login_required
def get_patient(patient_id):
    patient = patient_service.get_patient(patient_id)
    patient["screening_history"] = patient_service.get_patient_screening_history(patient_id)
    return jsonify(api_success(patient))
