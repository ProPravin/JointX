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

SCHEMA_VERSION = "3.1"

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
    # Habitual squatting (0/1) -- much of rural NER squats routinely for
    # work/domestic tasks, raising baseline knee flexion ROM well above
    # published Western normative values. Included so the model can learn
    # this context rather than reading normal-for-this-population ROM as
    # pathological; see config/model_config.py for the normative-data
    # provisionality note and validation/subgroups.py for the fairness
    # audit this feature enables (spec: subgroup/fairness audit).
    ("habitual_squatting", "patient"),
    # Functional tests (functional/feature_extraction.py)
    ("sit_to_stand_time", "functional"),
    ("squat_rom", "functional"),
    ("balance_stability", "functional"),
    ("turn_duration", "functional"),
    # Missingness indicators (spec: Data Integrity #A2) — always 0/1, never
    # NaN themselves, computed at fusion time from whether each block's row
    # existed in the DB. These let the model learn "this pattern is a missing
    # IMU block", not just see the block's raw features arrive as NaN with no
    # explicit signal of why.
    ("imu_present", "meta"),
    ("gait_present", "meta"),
    ("functional_present", "meta"),
    ("questionnaire_complete", "meta"),
    # Per-block capture quality, 0-1 (spec: Data Integrity #A2) — 0.0 when the
    # block is entirely absent, otherwise derived from real stored signals
    # (frame/sample counts, MediaPipe visibility, per-task quality flags).
    # See fusion/fusion.py for the exact computation and its documented
    # limitations (e.g. IMU saturation is not yet detected).
    ("imu_quality", "meta"),
    ("gait_quality", "meta"),
    ("functional_quality", "meta"),
]

FEATURE_NAMES = [name for name, _source in FEATURE_SCHEMA]

# Meta features (presence indicators, quality scores) are always computable
# at fusion time and are never genuinely missing, unlike sensor-derived
# features -- so they alone default to 0.0 rather than NaN.
_META_FEATURES = {"imu_present", "gait_present", "functional_present", "questionnaire_complete",
                   "imu_quality", "gait_quality", "functional_quality"}

# A missing sensor/patient/functional feature is enters the model as NaN, NOT
# 0.0 (spec: Data Integrity #A2). Coercing a missing reading to 0.0 -- e.g. a
# cadence that could not be measured because the camera failed -- makes the
# model read "0 steps per minute", which looks like severe immobility, not
# like a hardware failure. In a rural PHC, hardware/capture failure is the
# common case, so this distinction matters far more than it would in a lab.
# XGBoost handles NaN as "missing" natively and learns a per-split default
# direction for it, so no imputation is performed anywhere in this pipeline.
FEATURE_DEFAULTS = {name: (0.0 if name in _META_FEATURES else float("nan")) for name in FEATURE_NAMES}


def ordered_vector(feature_dict: dict) -> list:
    """
    Builds a list of floats in FEATURE_SCHEMA order from a feature dict.
    Deliberately does NOT coerce a missing/None value to 0.0 (see the
    FEATURE_DEFAULTS comment above) -- a value that is genuinely absent stays
    NaN, a legitimate zero reading stays 0.0. The two must never be conflated.
    """
    vector = []
    for name in FEATURE_NAMES:
        value = feature_dict.get(name)
        if value is None:
            value = FEATURE_DEFAULTS[name]
        vector.append(float(value))
    return vector


def validate_schema(feature_dict: dict):
    missing = [name for name in FEATURE_NAMES if name not in feature_dict]
    if missing:
        raise ValueError(f"Feature vector missing required fields: {missing}")
