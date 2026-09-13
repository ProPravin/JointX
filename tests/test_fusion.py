from fusion.fusion import build_unified_features
from fusion.feature_schema import FEATURE_NAMES, ordered_vector


def test_build_unified_features_order_matches_schema():
    gait = {"walking_speed": 1.0, "cadence": 100, "step_time": 0.6, "stride_time": 1.1,
            "left_right_asymmetry": 8, "knee_angle_rom": 40, "stance_swing_ratio": 1.6,
            "gait_cycle_variability": 5}
    imu = {"angular_velocity_rms": 50, "peak_angular_velocity": 90,
           "acceleration_rms": 0.4, "acceleration_variance": 0.03, "peak_acceleration": 1.2,
           "relative_joint_rom": 60, "movement_smoothness": 0.7, "movement_cycle_duration": 1.1}
    questionnaire = {"pain_score": 5, "stiffness_score": 3, "mobility_difficulty": 4,
                      "walking_difficulty": 3, "stairs_difficulty": 5,
                      "standing_difficulty": 2, "sit_to_stand_difficulty": 3}
    patient = {"age": 60, "height_cm": 165, "weight_kg": 70}
    functional = {"sit_to_stand_time": 8.0, "squat_rom": 55, "balance_stability": 0.1, "turn_duration": 3.0}

    fused = build_unified_features(gait, imu, questionnaire, patient, functional)

    assert fused["feature_names"] == FEATURE_NAMES
    assert len(fused["vector"]) == len(FEATURE_NAMES)
    assert fused["features"]["age"] == 60


def test_ordered_vector_defaults_missing_to_zero():
    vector = ordered_vector({"age": 40})
    assert len(vector) == len(FEATURE_NAMES)
    assert vector[FEATURE_NAMES.index("age")] == 40.0
    assert vector[FEATURE_NAMES.index("pain_score")] == 0.0
