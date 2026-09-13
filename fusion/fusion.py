"""
Multimodal feature fusion (spec section 9).

Gait Features + IMU Features + Patient Features + Functional-Test Features
-> Preprocessing -> Unified Feature Vector -> XGBoost.

Raw camera frames and raw IMU streams are NEVER passed to the model — only
the scalar features produced by computer_vision/feature_extraction.py,
imu/feature_extraction.py, and functional/feature_extraction.py.
"""
from fusion.feature_schema import FEATURE_NAMES, SCHEMA_VERSION, ordered_vector
from fusion.preprocessing import clip_features
from backend.utils.helpers import compute_bmi


def build_unified_features(gait: dict, imu: dict, questionnaire: dict, patient: dict, functional: dict = None) -> dict:
    """
    gait, imu: outputs of computer_vision/feature_extraction.extract_gait_features
               and imu/feature_extraction.extract_imu_features (must have
               data_quality_ok == True — caller is responsible for that check).
    questionnaire: row from the questionnaire table
    patient: row from the patients table
    functional: row from the functional_features table (sit-to-stand, squat,
               balance, turn) — optional; missing values default to 0.0.
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
        "sit_to_stand_time": functional.get("sit_to_stand_time"),
        "squat_rom": functional.get("squat_rom"),
        "balance_stability": functional.get("balance_stability"),
        "turn_duration": functional.get("turn_duration"),
    }

    cleaned = clip_features(raw)
    return {
        "schema_version": SCHEMA_VERSION,
        "feature_names": FEATURE_NAMES,
        "features": cleaned,
        "vector": ordered_vector(cleaned),
    }
