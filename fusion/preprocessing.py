"""
Preprocessing applied to the unified feature vector before it reaches
XGBoost. Kept intentionally simple (clipping only) for the prototype; a real
deployment should persist a fitted scikit-learn scaler from training/train.py
and load it here for both training and inference consistency.
"""

# Soft physiological/measurement bounds used to clip outliers rather than
# silently letting a bad sensor reading dominate the prediction.
CLIP_BOUNDS = {
    # IMU
    "acceleration_rms": (0, 5.0),
    "acceleration_variance": (0, 10.0),
    "peak_acceleration": (0, 10.0),
    "angular_velocity_rms": (0, 500),
    "peak_angular_velocity": (0, 1000),
    "relative_joint_rom": (0, 150),
    "movement_smoothness": (0, 1.0),
    "movement_cycle_duration": (0, 5.0),
    # Gait
    "cadence": (0, 160),
    "step_time": (0, 3.0),
    "stride_time": (0, 5.0),
    "walking_speed": (0, 3.0),
    "knee_angle_rom": (0, 120),
    "stance_swing_ratio": (0, 5.0),
    "left_right_asymmetry": (0, 100),
    "gait_cycle_variability": (0, 100),
    # Patient
    "age": (0, 120),
    "bmi": (10, 60),
    "pain_score": (0, 10),
    "stiffness_score": (0, 10),
    "mobility_score": (0, 10),
    # Functional
    "sit_to_stand_time": (0, 60),
    "squat_rom": (0, 120),
    "balance_stability": (0, 5.0),
    "turn_duration": (0, 30),
}


def clip_features(feature_dict: dict) -> dict:
    clipped = {}
    for name, value in feature_dict.items():
        if value is None:
            clipped[name] = None
            continue
        lo, hi = CLIP_BOUNDS.get(name, (None, None))
        if lo is not None:
            value = max(lo, min(hi, value))
        clipped[name] = value
    return clipped
