"""
JointX top-level configuration loader.
Reads environment variables (see .env.example) and exposes a Config object
used by app.py. Keeps secrets out of source code.
"""
import os
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    # Flask
    SECRET_KEY = os.environ.get("JOINTX_SECRET_KEY", "dev-insecure-key-change-me")
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

    # Sync
    SYNC_ENDPOINT = os.environ.get("JOINTX_SYNC_ENDPOINT", "")
    SYNC_API_KEY = os.environ.get("JOINTX_SYNC_API_KEY", "")

    # Logging
    LOG_DIR = os.path.join(BASE_DIR, "logs")
    LOG_LEVEL = os.environ.get("JOINTX_LOG_LEVEL", "INFO")

    # Clinical safety disclaimers (single source of truth, referenced everywhere)
    DISCLAIMER_GENERAL = (
        "JointX provides preliminary OA risk screening and does not replace "
        "professional clinical diagnosis."
    )
    DISCLAIMER_FURTHER_EVAL = "Further clinical evaluation is recommended."
    DISCLAIMER_DEMO_DATA = "DEMO DATA — NOT CLINICAL DATA"
    DISCLAIMER_PROTOTYPE_MODEL = "Demo/Prototype Output — Not Clinical Prediction"
