"""Runs multimodal feature fusion for a screening and persists the result."""
from database.database import get_cursor
from backend.utils.helpers import to_json
from backend.utils.error_handler import JointXError
from fusion.fusion import build_unified_features
from fusion.feature_schema import SCHEMA_VERSION


def fuse_screening_features(screening_id: int) -> dict:
    """
    Fuses whatever blocks a screening actually has into a feature vector.
    This deliberately does NOT require every block to be present or
    high-quality (spec: Data Integrity #A2) -- a screening with, say, only
    IMU + questionnaire data still fuses, with the missing gait/functional
    features recorded as NaN and gait_present/functional_present as 0.
    Whether that is enough to actually PREDICT on is decided later, by the
    refusal gate in backend/services/prediction_service.py -- fusion's job is
    only to build an honest record of what was and wasn't captured.
    """
    with get_cursor() as cur:
        cur.execute("SELECT * FROM screenings WHERE id = ?", (screening_id,))
        screening = cur.fetchone()
        if not screening:
            raise JointXError("Screening not found", status_code=404)

        cur.execute("SELECT * FROM patients WHERE id = ?", (screening["patient_id"],))
        patient = dict(cur.fetchone() or {})

        cur.execute("SELECT * FROM questionnaire WHERE screening_id = ?", (screening_id,))
        row = cur.fetchone()
        questionnaire = dict(row) if row else None

        cur.execute("SELECT * FROM gait_features WHERE screening_id = ?", (screening_id,))
        row = cur.fetchone()
        gait = dict(row) if row else None

        cur.execute("SELECT * FROM imu_features WHERE screening_id = ?", (screening_id,))
        row = cur.fetchone()
        imu = dict(row) if row else None

        cur.execute("SELECT * FROM functional_features WHERE screening_id = ?", (screening_id,))
        row = cur.fetchone()
        functional = dict(row) if row else None

    fused = build_unified_features(gait, imu, questionnaire, patient, functional)

    with get_cursor(commit=True) as cur:
        cur.execute("DELETE FROM fused_features WHERE screening_id = ?", (screening_id,))
        cur.execute(
            """INSERT INTO fused_features (screening_id, feature_json, schema_version)
               VALUES (?, ?, ?)""",
            (screening_id, to_json(fused), SCHEMA_VERSION),
        )

    return fused
