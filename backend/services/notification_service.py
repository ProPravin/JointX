"""
Server-side SMS/WhatsApp delivery (Tier 1 production integration).

Previously, "sending" a report only opened a wa.me/sms: link on the WORKER'S
OWN phone/browser -- nothing was actually transmitted by the server, and
there was no delivery confirmation or record of what was sent. This module
adds a real backend send path via Twilio, used when configured; when it
isn't, callers fall back to the existing client-side deep-link behaviour
(frontend/templates/reports.html) rather than silently failing.

Every send attempt -- success or failure -- is written to audit_log via the
caller (backend/routes/report_routes.py), never with the message BODY
(no clinical free-text in logs/audit rows -- only that a send of a given
channel/status happened for a given screening).
"""
from config.settings import Config
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class NotificationError(Exception):
    def __init__(self, message):
        super().__init__(message)
        self.message = message


def is_configured() -> bool:
    return bool(Config.TWILIO_ACCOUNT_SID and Config.TWILIO_AUTH_TOKEN)


def _client():
    try:
        from twilio.rest import Client
    except ImportError as e:
        raise NotificationError(
            "Twilio credentials are configured but the 'twilio' package is not installed. "
            "Run: pip install twilio"
        ) from e
    return Client(Config.TWILIO_ACCOUNT_SID, Config.TWILIO_AUTH_TOKEN)


def send_sms(to_phone: str, message: str) -> dict:
    """Returns {"sent": bool, "channel": "sms", "provider_id": str|None, "error": str|None}."""
    if not is_configured():
        raise NotificationError("SMS/WhatsApp sending is not configured (JOINTX_TWILIO_* env vars unset)")
    if not Config.TWILIO_SMS_FROM:
        raise NotificationError("JOINTX_TWILIO_SMS_FROM is not configured")

    try:
        client = _client()
        msg = client.messages.create(to=to_phone, from_=Config.TWILIO_SMS_FROM, body=message)
        logger.info("SMS sent via Twilio, sid=%s", msg.sid)
        return {"sent": True, "channel": "sms", "provider_id": msg.sid, "error": None}
    except Exception as e:  # noqa: BLE001 -- Twilio raises its own exception hierarchy
        logger.warning("SMS send failed: %s", e)
        return {"sent": False, "channel": "sms", "provider_id": None, "error": str(e)}


def send_whatsapp(to_phone: str, message: str) -> dict:
    """Returns {"sent": bool, "channel": "whatsapp", "provider_id": str|None, "error": str|None}."""
    if not is_configured():
        raise NotificationError("SMS/WhatsApp sending is not configured (JOINTX_TWILIO_* env vars unset)")
    if not Config.TWILIO_WHATSAPP_FROM:
        raise NotificationError("JOINTX_TWILIO_WHATSAPP_FROM is not configured")

    to_whatsapp = to_phone if to_phone.startswith("whatsapp:") else f"whatsapp:{to_phone}"
    try:
        client = _client()
        msg = client.messages.create(to=to_whatsapp, from_=Config.TWILIO_WHATSAPP_FROM, body=message)
        logger.info("WhatsApp message sent via Twilio, sid=%s", msg.sid)
        return {"sent": True, "channel": "whatsapp", "provider_id": msg.sid, "error": None}
    except Exception as e:  # noqa: BLE001
        logger.warning("WhatsApp send failed: %s", e)
        return {"sent": False, "channel": "whatsapp", "provider_id": None, "error": str(e)}
