"""
Multimodal feature fusion (spec section 9).

Gait Features + IMU Features + Patient Features + Functional-Test Features
-> Preprocessing -> Unified Feature Vector -> XGBoost.

Raw camera frames and raw IMU streams are NEVER passed to the model — only
the scalar features produced by computer_vision/feature_extraction.py,
imu/feature_extraction.py, and functional/feature_extraction.py.
"""
from config.model_config import MIN_POSE_LANDMARK_VISIBILITY, MIN_POSE_FRAMES, MIN_IMU_SAMPLES
from fusion.feature_schema import FEATURE_NAMES, SCHEMA_VERSION, ordered_vector
from fusion.preprocessing import clip_features
from backend.utils.helpers import compute_bmi


def _gait_quality(gait: dict) -> float:
    """
    0-1 capture quality for the gait block, from real stored signals only:
    mean MediaPipe landmark visibility and how many usable frames were
    captured relative to the minimum. Absent block or a failed
    data_quality_ok check both score 0.0 -- a low-confidence capture is not
    worth partial credit here (spec: Data Integrity #A2).
    """
    if not gait or not gait.get("data_quality_ok"):
        return 0.0
    visibility = gait.get("mean_visibility") or 0.0
    frame_adequacy = min(1.0, (gait.get("frames_used") or 0) / MIN_POSE_FRAMES)
    return max(0.0, min(1.0, visibility * frame_adequacy))


def _imu_quality(imu: dict) -> float:
    """
    0-1 capture quality for the IMU block, from sample-count sufficiency on
    both sensors. NOTE: this does not yet detect accelerometer/gyroscope
    saturation (clipped readings) because raw per-sample sensor values are
    not persisted -- only extracted features are. That is a documented gap,
    not fabricated precision; saturation detection needs raw_json to retain
    the sample stream, which is a larger storage change than this pass makes.
    """
    if not imu or not imu.get("data_quality_ok"):
        return 0.0
    left = imu.get("left_samples") or 0
    right = imu.get("right_samples") or 0
    adequacy = min(1.0, min(left, right) / MIN_IMU_SAMPLES)
    return max(0.0, min(1.0, adequacy))


def _functional_quality(functional: dict) -> float:
    """0-1 fraction of the four functional sub-tasks that passed their own quality check."""
    if not functional:
        return 0.0
    flags = [
        functional.get("sit_to_stand_ok"),
        functional.get("squat_ok"),
        functional.get("balance_ok"),
        functional.get("turn_ok"),
    ]
    completed = [f for f in flags if f is not None]
    if not completed:
        return 0.0
    return sum(1 for f in completed if f) / len(flags)


def build_unified_features(gait: dict, imu: dict, questionnaire: dict, patient: dict, functional: dict = None) -> dict:
    """
    gait, imu: outputs of computer_vision/feature_extraction.extract_gait_features
               and imu/feature_extraction.extract_imu_features. Either may be
               None or of low quality -- this function no longer requires
               data_quality_ok == True; it records presence/quality
               indicators instead and lets the REFUSAL GATE in
               backend/services/prediction_service.py decide whether there is
               enough to predict on (spec: Data Integrity #A2).
    questionnaire: row from the questionnaire table, or None if not completed.
    patient: row from the patients table
    functional: row from the functional_features table (sit-to-stand, squat,
               balance, turn) — optional; a missing/incomplete block reduces
               functional_quality rather than being silently zero-filled.
    """
    functional = functional or {}

    mobility_score = None
    if questionnaire:
        parts = [
            questionnaire.get("mobility_difficulty"),
            questionnaire.get("walking_difficulty"),
            questionnaire.get("stairs_difficulty"),
            questionnaire.get("standing_difficulty"),
            questionnaire.get("sit_to_stand_difficulty"),
        ]
        parts = [p for p in parts if p is not None]
        mobility_score = sum(parts) / len(parts) if parts else None

    bmi = compute_bmi(patient.get("height_cm"), patient.get("weight_kg")) if patient else None

    raw = {
        "acceleration_rms": imu.get("acceleration_rms") if imu else None,
        "acceleration_variance": imu.get("acceleration_variance") if imu else None,
        "peak_acceleration": imu.get("peak_acceleration") if imu else None,
        "angular_velocity_rms": imu.get("angular_velocity_rms") if imu else None,
        "peak_angular_velocity": imu.get("peak_angular_velocity") if imu else None,
        "relative_joint_rom": imu.get("relative_joint_rom") if imu else None,
        "movement_smoothness": imu.get("movement_smoothness") if imu else None,
        "movement_cycle_duration": imu.get("movement_cycle_duration") if imu else None,
        "cadence": gait.get("cadence") if gait else None,
        "step_time": gait.get("step_time") if gait else None,
        "stride_time": gait.get("stride_time") if gait else None,
        "walking_speed": gait.get("walking_speed") if gait else None,
        "knee_angle_rom": gait.get("knee_angle_rom") if gait else None,
        "stance_swing_ratio": gait.get("stance_swing_ratio") if gait else None,
        "left_right_asymmetry": gait.get("left_right_asymmetry") if gait else None,
        "gait_cycle_variability": gait.get("gait_cycle_variability") if gait else None,
        "age": patient.get("age") if patient else None,
        "bmi": bmi,
        "pain_score": questionnaire.get("pain_score") if questionnaire else None,
        "stiffness_score": questionnaire.get("stiffness_score") if questionnaire else None,
        "mobility_score": mobility_score,
        "habitual_squatting": questionnaire.get("habitual_squatting") if questionnaire else None,
        "sit_to_stand_time": functional.get("sit_to_stand_time"),
        "squat_rom": functional.get("squat_rom"),
        "balance_stability": functional.get("balance_stability"),
        "turn_duration": functional.get("turn_duration"),
        "imu_present": int(bool(imu)),
        "gait_present": int(bool(gait)),
        "functional_present": int(bool(functional)),
        "questionnaire_complete": int(bool(questionnaire)),
        "imu_quality": _imu_quality(imu),
        "gait_quality": _gait_quality(gait),
        "functional_quality": _functional_quality(functional),
    }

    cleaned = clip_features(raw)
    return {
        "schema_version": SCHEMA_VERSION,
        "feature_names": FEATURE_NAMES,
        "features": cleaned,
        "vector": ordered_vector(cleaned),
    }
