"""
JointX top-level configuration loader.
Reads environment variables (see .env.example) and exposes a Config object
used by app.py. Keeps secrets out of source code.
"""
import os
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


INSECURE_DEFAULT_SECRET_KEY = "dev-insecure-key-change-me"

# Known placeholder values that must never reach a production boot -- not
# just this module's own fallback, but also .env.example's placeholder text,
# since a deployment that copies .env.example to .env without editing it is
# exactly the failure mode this guard exists to catch.
_KNOWN_INSECURE_SECRET_KEYS = {
    INSECURE_DEFAULT_SECRET_KEY,
    "change-this-to-a-long-random-string",
    "",
}


class Config:
    # Flask
    SECRET_KEY = os.environ.get("JOINTX_SECRET_KEY", INSECURE_DEFAULT_SECRET_KEY)
    DEBUG = os.environ.get("JOINTX_DEBUG", "true").lower() == "true"
    HOST = os.environ.get("JOINTX_HOST", "0.0.0.0")
    PORT = int(os.environ.get("JOINTX_PORT", "5000"))

    # Database
    DATABASE_PATH = os.environ.get(
        "JOINTX_DB_PATH", os.path.join(BASE_DIR, "data", "jointx.db")
    )
    SCHEMA_PATH = os.path.join(BASE_DIR, "database", "schema.sql")

    # Session
    SESSION_LIFETIME_MINUTES = int(os.environ.get("JOINTX_SESSION_MINUTES", "60"))
    # Only set this true once the app is actually served over HTTPS — a
    # secure-only cookie is silently dropped by browsers over plain HTTP,
    # which would make login appear to succeed but never actually persist.
    SESSION_COOKIE_SECURE = os.environ.get("JOINTX_SESSION_SECURE", "false").lower() == "true"

    # Account lockout (brute-force login protection)
    MAX_FAILED_LOGIN_ATTEMPTS = int(os.environ.get("JOINTX_MAX_LOGIN_ATTEMPTS", "5"))
    LOCKOUT_MINUTES = int(os.environ.get("JOINTX_LOCKOUT_MINUTES", "15"))

    # Demo / prototype mode
    DEMO_MODE = os.environ.get("JOINTX_DEMO_MODE", "true").lower() == "true"

    # Hardware
    CAMERA_INDEX = int(os.environ.get("JOINTX_CAMERA_INDEX", "0"))
    ESP32_HOST = os.environ.get("JOINTX_ESP32_HOST", "")  # e.g. "http://192.168.4.1"
    ESP32_TIMEOUT_S = float(os.environ.get("JOINTX_ESP32_TIMEOUT_S", "2.0"))

    # ML model
    MODEL_DIR = os.path.join(BASE_DIR, "ml", "models")
    MODEL_PATH = os.environ.get(
        "JOINTX_MODEL_PATH", os.path.join(MODEL_DIR, "jointx_xgb_model.json")
    )

    # Sync (this device -> central server, see central_server/ for the
    # reference receiver implementation)
    SYNC_ENDPOINT = os.environ.get("JOINTX_SYNC_ENDPOINT", "")
    SYNC_API_KEY = os.environ.get("JOINTX_SYNC_API_KEY", "")
    # Identifies which field device/facility a synced record came from, so the
    # central server can tell PHC devices apart. Defaults to the machine's own
    # hostname; set explicitly for a stable identifier that survives reimaging.
    _default_hostname = os.uname().nodename if hasattr(os, "uname") else os.environ.get("COMPUTERNAME", "unknown-device")
    DEVICE_ID = os.environ.get("JOINTX_DEVICE_ID", _default_hostname)

    # SMS/WhatsApp delivery (Twilio). When unset, report-sending falls back to
    # opening a wa.me/sms: deep link on the worker's own device instead of a
    # real server-side send -- see backend/services/notification_service.py.
    TWILIO_ACCOUNT_SID = os.environ.get("JOINTX_TWILIO_ACCOUNT_SID", "")
    TWILIO_AUTH_TOKEN = os.environ.get("JOINTX_TWILIO_AUTH_TOKEN", "")
    TWILIO_SMS_FROM = os.environ.get("JOINTX_TWILIO_SMS_FROM", "")  # e.g. "+15551234567"
    TWILIO_WHATSAPP_FROM = os.environ.get("JOINTX_TWILIO_WHATSAPP_FROM", "")  # e.g. "whatsapp:+14155238886"

    # Local database backups (see tools/backup_db.py)
    BACKUP_DIR = os.environ.get("JOINTX_BACKUP_DIR", os.path.join(BASE_DIR, "backups"))
    BACKUP_RETENTION_COUNT = int(os.environ.get("JOINTX_BACKUP_RETENTION_COUNT", "30"))
    # Optional off-device copy. Uses boto3's own standard AWS credential chain
    # (env vars / ~/.aws/credentials / instance role) -- never store AWS keys
    # in this app's own config.
    BACKUP_S3_BUCKET = os.environ.get("JOINTX_BACKUP_S3_BUCKET", "")

    # Logging
    LOG_DIR = os.path.join(BASE_DIR, "logs")
    LOG_LEVEL = os.environ.get("JOINTX_LOG_LEVEL", "INFO")

    @classmethod
    def validate_for_production(cls):
        """
        Startup guard: refuses to run with unsafe defaults once DEMO_MODE is
        off, i.e. once this is presumed to be a real deployment rather than a
        demo/dev instance. Never silently allows an insecure production boot.
        """
        if cls.DEMO_MODE:
            return

        fatal_errors = []
        if cls.SECRET_KEY in _KNOWN_INSECURE_SECRET_KEYS:
            fatal_errors.append(
                "JOINTX_SECRET_KEY is still a known placeholder/default value. Generate a real one, e.g.:\n"
                "    python -c \"import secrets; print(secrets.token_hex(32))\"\n"
                "and set JOINTX_SECRET_KEY to it."
            )
        if fatal_errors:
            raise RuntimeError(
                "Refusing to start with DEMO_MODE=false and unsafe configuration:\n- "
                + "\n- ".join(fatal_errors)
            )

        if not cls.SESSION_COOKIE_SECURE and not cls.DEBUG:
            # Not fatal on its own -- some production deployments terminate
            # HTTPS at a reverse proxy in front of this app -- but worth a
            # loud warning since the common mistake is simply forgetting it.
            from backend.utils.logger import get_logger

            get_logger(__name__).warning(
                "JOINTX_SESSION_SECURE is false outside DEBUG mode -- confirm this "
                "deployment is actually behind HTTPS, or session cookies are sent "
                "in plaintext."
            )

    # Clinical safety disclaimers (single source of truth, referenced everywhere)
    DISCLAIMER_GENERAL = (
        "JointX provides preliminary OA risk screening and does not replace "
        "professional clinical diagnosis."
    )
    DISCLAIMER_FURTHER_EVAL = "Further clinical evaluation is recommended."
    DISCLAIMER_DEMO_DATA = "DEMO DATA — NOT CLINICAL DATA"
    DISCLAIMER_PROTOTYPE_MODEL = "Demo/Prototype Output — Not Clinical Prediction"
