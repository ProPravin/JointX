import pytest

from config.settings import Config
from backend.services import notification_service


def test_not_configured_by_default():
    original = (Config.TWILIO_ACCOUNT_SID, Config.TWILIO_AUTH_TOKEN)
    try:
        Config.TWILIO_ACCOUNT_SID, Config.TWILIO_AUTH_TOKEN = "", ""
        assert notification_service.is_configured() is False
    finally:
        Config.TWILIO_ACCOUNT_SID, Config.TWILIO_AUTH_TOKEN = original


def test_send_sms_raises_when_not_configured():
    original = (Config.TWILIO_ACCOUNT_SID, Config.TWILIO_AUTH_TOKEN)
    try:
        Config.TWILIO_ACCOUNT_SID, Config.TWILIO_AUTH_TOKEN = "", ""
        with pytest.raises(notification_service.NotificationError, match="not configured"):
            notification_service.send_sms("+15551234567", "test")
    finally:
        Config.TWILIO_ACCOUNT_SID, Config.TWILIO_AUTH_TOKEN = original


def test_send_report_endpoint_falls_back_when_not_configured(logged_in_client):
    from config.settings import Config as C

    original = (C.TWILIO_ACCOUNT_SID, C.TWILIO_AUTH_TOKEN)
    try:
        C.TWILIO_ACCOUNT_SID, C.TWILIO_AUTH_TOKEN = "", ""
        res = logged_in_client.post(
            "/api/reports/1/send",
            json={"channel": "sms", "to_phone": "+15551234567", "message": "test report"},
        )
        assert res.status_code == 200
        body = res.get_json()
        assert body["success"] is True
        assert body["data"]["configured"] is False
    finally:
        C.TWILIO_ACCOUNT_SID, C.TWILIO_AUTH_TOKEN = original
