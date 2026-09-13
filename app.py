"""
JointX entry point.

Run with:
    python app.py

Runs on Raspberry Pi as well as any dev machine. Offline-first: no internet
connection is required for any core screening functionality.
"""
from datetime import timedelta

from flask import Flask, render_template, session, redirect, url_for

from config.settings import Config
from database.database import init_db, seed_default_worker
from backend.utils.error_handler import register_error_handlers
from backend.utils.logger import get_logger

from backend.routes.auth_routes import auth_bp
from backend.routes.patient_routes import patient_bp
from backend.routes.screening_routes import screening_bp
from backend.routes.questionnaire_routes import questionnaire_bp
from backend.routes.gait_routes import gait_bp
from backend.routes.imu_routes import imu_bp
from backend.routes.functional_routes import functional_bp
from backend.routes.prediction_routes import prediction_bp
from backend.routes.review_routes import review_bp
from backend.routes.referral_routes import referral_bp
from backend.routes.report_routes import report_bp
from backend.routes.device_routes import device_bp
from backend.routes.sync_routes import sync_bp
from backend.routes.settings_routes import settings_bp
from config.roles import tier_for_role, label_for_role
from config.i18n import SUPPORTED_LANGUAGES, DEFAULT_LANGUAGE

logger = get_logger(__name__)


def create_app():
    app = Flask(
        __name__,
        template_folder="frontend/templates",
        static_folder="frontend/static",
    )
    app.config["SECRET_KEY"] = Config.SECRET_KEY
    app.permanent_session_lifetime = timedelta(minutes=Config.SESSION_LIFETIME_MINUTES)

    # --- API blueprints ---
    for bp in (
        auth_bp,
        patient_bp,
        screening_bp,
        questionnaire_bp,
        gait_bp,
        imu_bp,
        functional_bp,
        prediction_bp,
        review_bp,
        referral_bp,
        report_bp,
        device_bp,
        sync_bp,
        settings_bp,
    ):
        app.register_blueprint(bp)

    register_error_handlers(app)

    @app.context_processor
    def inject_role_and_language():
        role = session.get("worker_role")
        return {
            "role_tier": tier_for_role(role) if role else None,
            "role_label": label_for_role(role) if role else None,
            "ui_language": session.get("worker_language", DEFAULT_LANGUAGE),
            "supported_languages": SUPPORTED_LANGUAGES,
        }

    # --- Page routes (server-rendered shell; JS in frontend/static/js
    #     drives the actual API calls documented above) ---
    @app.route("/")
    def index():
        if session.get("worker_id"):
            return redirect(url_for("dashboard"))
        return redirect(url_for("login_page"))

    @app.route("/login")
    def login_page():
        return render_template("login.html", demo_mode=Config.DEMO_MODE)

    @app.route("/dashboard")
    def dashboard():
        return render_template("dashboard.html", worker_name=session.get("worker_name"))

    @app.route("/patients")
    def patients_page():
        return render_template("patients.html")

    @app.route("/patients/new")
    def patient_form_page():
        return render_template("patient_form.html")

    @app.route("/patients/<int:patient_id>")
    def patient_profile_page(patient_id):
        return render_template("patient_profile.html", patient_id=patient_id)

    @app.route("/screening/<int:screening_id>/questionnaire")
    def questionnaire_page(screening_id):
        return render_template("questionnaire.html", screening_id=screening_id)

    @app.route("/screening/<int:screening_id>/gait")
    def gait_page(screening_id):
        return render_template("gait_analysis.html", screening_id=screening_id, demo_mode=Config.DEMO_MODE)

    @app.route("/screening/<int:screening_id>/imu")
    def imu_page(screening_id):
        return render_template("imu_analysis.html", screening_id=screening_id, demo_mode=Config.DEMO_MODE)

    @app.route("/screening/<int:screening_id>/functional")
    def functional_page(screening_id):
        return render_template("functional_tests.html", screening_id=screening_id, demo_mode=Config.DEMO_MODE)

    @app.route("/screening/new/<int:patient_id>")
    def new_screening_page(patient_id):
        return render_template("screening.html", patient_id=patient_id, demo_mode=Config.DEMO_MODE)

    @app.route("/screening/<int:screening_id>/processing")
    def processing_page(screening_id):
        return render_template("processing.html", screening_id=screening_id)

    @app.route("/screening/<int:screening_id>/results")
    def results_page(screening_id):
        return render_template(
            "results.html",
            screening_id=screening_id,
            disclaimer=Config.DISCLAIMER_GENERAL,
            further_eval=Config.DISCLAIMER_FURTHER_EVAL,
        )

    @app.route("/screening/<int:screening_id>/review")
    def review_page(screening_id):
        return render_template("review.html", screening_id=screening_id)

    @app.route("/referrals")
    def referrals_page():
        return render_template("referrals.html")

    @app.route("/reports/<int:screening_id>")
    def reports_page(screening_id):
        return render_template("reports.html", screening_id=screening_id)

    @app.route("/device-status")
    def device_status_page():
        return render_template("device_status.html")

    with app.app_context():
        init_db()
        seed_default_worker()

    logger.info("JointX started. DEMO_MODE=%s", Config.DEMO_MODE)
    return app


app = create_app()

if __name__ == "__main__":
    app.run(host=Config.HOST, port=Config.PORT, debug=Config.DEBUG)
