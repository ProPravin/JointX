from flask import Blueprint, jsonify, Response, session, request

from backend.services.report_service import build_report
from backend.services.sync_service import enqueue_screening_for_sync
from backend.services.screening_service import complete_screening
from backend.services import audit_service, notification_service
from backend.utils.security import login_required
from backend.utils.helpers import api_success, api_error
from backend.utils.validators import require_fields, validate_choice
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


@report_bp.route("/<int:screening_id>/send", methods=["POST"])
@login_required
def send_report(screening_id):
    """
    Real server-side SMS/WhatsApp delivery, when Twilio is configured
    (Config.TWILIO_*). If it isn't configured, returns configured=False so
    the frontend falls back to its existing wa.me/sms: deep-link behaviour
    (see frontend/templates/reports.html) rather than pretending to send.
    The message BODY is never written to the audit log -- only that a send
    of a given channel/status happened.
    """
    data = request.get_json(force=True, silent=True) or {}
    require_fields(data, ["channel", "to_phone", "message"])
    validate_choice(data["channel"], ["sms", "whatsapp"], "channel")

    if not notification_service.is_configured():
        return jsonify(api_success({"configured": False}, "Server-side sending not configured; use the device share link instead"))

    try:
        if data["channel"] == "sms":
            result = notification_service.send_sms(data["to_phone"], data["message"])
        else:
            result = notification_service.send_whatsapp(data["to_phone"], data["message"])
    except notification_service.NotificationError as e:
        return jsonify(api_error(e.message)), 422

    result["configured"] = True
    audit_service.log_action(
        session.get("worker_id"), "REPORT_SENT", "screening", screening_id,
        {"channel": result["channel"], "sent": result["sent"]},
    )
    if not result["sent"]:
        return jsonify(api_error(result.get("error") or "Send failed")), 502
    return jsonify(api_success(result, "Report sent"))


@report_bp.route("/<int:screening_id>/finalize", methods=["POST"])
@login_required
def finalize_report(screening_id):
    complete_screening(screening_id)
    enqueue_screening_for_sync(screening_id)
    audit_service.log_action(session.get("worker_id"), "REPORT_FINALIZED", "screening", screening_id)
    return jsonify(api_success(message="Screening completed and queued for sync"))
