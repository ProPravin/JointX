from flask import Blueprint, jsonify, Response

from backend.services.report_service import build_report
from backend.services.sync_service import enqueue_screening_for_sync
from backend.services.screening_service import complete_screening
from backend.utils.security import login_required
from backend.utils.helpers import api_success
from reports.report_generator import render_text_report

report_bp = Blueprint("reports", __name__, url_prefix="/api/reports")


@report_bp.route("/<int:screening_id>", methods=["GET"])
@login_required
def get_report(screening_id):
    report = build_report(screening_id)
    return jsonify(api_success(report))


@report_bp.route("/<int:screening_id>/text", methods=["GET"])
@login_required
def get_report_text(screening_id):
    text = render_text_report(screening_id)
    return Response(text, mimetype="text/plain")


@report_bp.route("/<int:screening_id>/finalize", methods=["POST"])
@login_required
def finalize_report(screening_id):
    complete_screening(screening_id)
    enqueue_screening_for_sync(screening_id)
    return jsonify(api_success(message="Screening completed and queued for sync"))
