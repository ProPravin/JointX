"""
Model-specific configuration: risk thresholds, XGBoost hyperparameters used
during training, and SHAP display settings.

NOTE: RISK_THRESHOLDS below operate on a model-output risk score in [0, 1].
These thresholds are placeholders for prototype/demo use only and are NOT
clinically validated. They must be revisited once a real trained, evaluated
model exists (see training/README.md).
"""

RISK_THRESHOLDS = {
    "LOW": 0.33,       # score < 0.33  -> LOW
    "MODERATE": 0.66,  # 0.33 <= score < 0.66 -> MODERATE
    # score >= 0.66 -> HIGH
}

RISK_LABELS = ["LOW", "MODERATE", "HIGH"]

XGBOOST_TRAIN_PARAMS = {
    "objective": "multi:softprob",
    "num_class": 3,
    "eval_metric": "mlogloss",
    "max_depth": 4,
    "eta": 0.1,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "seed": 42,
}

SHAP_TOP_N_FEATURES = 6

# Minimum data-quality thresholds required before a prediction is allowed
MIN_POSE_LANDMARK_VISIBILITY = 0.5   # mean MediaPipe visibility score
MIN_POSE_FRAMES = 30                 # minimum usable frames in a gait test
MIN_IMU_SAMPLES = 50                 # minimum samples per IMU sensor
