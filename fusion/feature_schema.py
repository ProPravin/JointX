"""
Centralized feature schema for JointX (spec section 9).

This is the SINGLE SOURCE OF TRUTH for feature names and order used by:
  - fusion/fusion.py     (builds the vector at inference time)
  - training/train.py    (builds the vector from the training dataset)
  - ml/predictor.py       (feeds the vector to XGBoost)
  - ml/shap_explainer.py  (labels SHAP contributions)

Never construct a raw feature list/array anywhere else in the codebase.

25-feature set: 8 IMU + 8 camera/gait + 5 patient + 4 functional-test
features, derived from synchronized wearable IMUs (MPU6050 x2), camera-based
gait analysis (MediaPipe), patient-reported screening fields, and four short
functional tasks (sit-to-stand, squat, balance, turn).
"""

SCHEMA_VERSION = "2.0"

# Ordered list of (feature_name, source) — source is informational only.
FEATURE_SCHEMA = [
    # IMU (imu/feature_extraction.py) — thigh + shank MPU6050 streams
    ("acceleration_rms", "imu"),
    ("acceleration_variance", "imu"),
    ("peak_acceleration", "imu"),
    ("angular_velocity_rms", "imu"),
    ("peak_angular_velocity", "imu"),
    ("relative_joint_rom", "imu"),
    ("movement_smoothness", "imu"),
    ("movement_cycle_duration", "imu"),
    # Gait (computer_vision/feature_extraction.py) — MediaPipe pose landmarks
    ("cadence", "gait"),
    ("step_time", "gait"),
    ("stride_time", "gait"),
    ("walking_speed", "gait"),
    ("knee_angle_rom", "gait"),
    ("stance_swing_ratio", "gait"),
    ("left_right_asymmetry", "gait"),
    ("gait_cycle_variability", "gait"),
    # Patient (registration/questionnaire screens)
    ("age", "patient"),
    ("bmi", "patient"),
    ("pain_score", "patient"),
    ("stiffness_score", "patient"),
    ("mobility_score", "patient"),
    # Functional tests (functional/feature_extraction.py)
    ("sit_to_stand_time", "functional"),
    ("squat_rom", "functional"),
    ("balance_stability", "functional"),
    ("turn_duration", "functional"),
]

FEATURE_NAMES = [name for name, _source in FEATURE_SCHEMA]

# Sensible fallback values used only when a given input is genuinely missing
# after a best-effort extraction (never used to fabricate a "good" reading;
# the pipeline still refuses to predict if quality checks failed upstream).
FEATURE_DEFAULTS = {name: 0.0 for name in FEATURE_NAMES}


def ordered_vector(feature_dict: dict) -> list:
    """Builds a list of floats in FEATURE_SCHEMA order from a feature dict."""
    return [
        float(feature_dict.get(name, FEATURE_DEFAULTS[name]) or 0.0)
        for name in FEATURE_NAMES
    ]


def validate_schema(feature_dict: dict):
    missing = [name for name in FEATURE_NAMES if name not in feature_dict]
    if missing:
        raise ValueError(f"Feature vector missing required fields: {missing}")
