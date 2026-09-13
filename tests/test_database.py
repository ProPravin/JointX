from database.database import get_cursor


def test_schema_creates_core_tables(app):
    with app.app_context():
        with get_cursor() as cur:
            cur.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
            tables = {row["name"] for row in cur.fetchall()}

    expected = {
        "patients", "screenings", "questionnaire", "gait_features",
        "imu_features", "fused_features", "predictions", "shap_explanations",
        "healthcare_reviews", "referrals", "sync_queue", "device_status",
        "healthcare_workers",
    }
    assert expected.issubset(tables)


def test_default_worker_seeded(app):
    with app.app_context():
        with get_cursor() as cur:
            cur.execute("SELECT COUNT(*) c FROM healthcare_workers")
            assert cur.fetchone()["c"] >= 1
