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

# REFUSAL GATE (spec: Data Integrity #A2): the pipeline does not predict at
# all -- rather than silently degrading -- when there isn't enough captured
# data to trust a prediction. A screening below this bar is recorded with
# refused=1 and a human-readable refusal_reason, never silently discarded.
MIN_FEATURE_BLOCKS_PRESENT = 2       # of {imu, gait, functional, questionnaire}
MIN_OVERALL_CAPTURE_QUALITY = 0.4    # mean quality across the blocks that ARE present

# HABITUAL SQUATTING / NORMATIVE DATA CAVEAT (spec: subgroup fairness audit):
# published joint-ROM normative ranges (including CLIP_BOUNDS in
# fusion/preprocessing.py and the heuristic weights above) are drawn from
# general/Western clinical literature. Much of rural North-Eastern-Region
# India squats routinely for agricultural and domestic work, which raises
# baseline knee flexion ROM well above those published norms in people with
# perfectly healthy joints. Any risk threshold derived from Western
# normative data is therefore PROVISIONAL for this population until local
# normative values exist from real NER field data -- see
# validation/subgroups.py, which specifically checks whether model
# sensitivity/specificity differs by habitual_squatting status, and
# docs/DATA_COLLECTION.md for the enrollment target this depends on.

# MINIMUM-N GATE (honest evaluation for small N): below these thresholds,
# evaluate.py must prefix its output "STATISTICALLY UNRELIABLE -- N TOO
# SMALL" and /api/model/performance must refuse to serve the numbers to the
# dashboard, rather than reporting a precise-looking metric computed from a
# handful of people.
MIN_SUBJECTS_N = 40
MIN_MINORITY_CLASS_SUBJECTS_N = 10

# CALIBRATION GATE (spec: numeric score honesty): XGBoost's raw softmax
# output is not a calibrated probability -- "risk score 62" implies
# precision the system does not have unless a calibrator has been fitted
# and its Brier score checked. A Brier score at or below this threshold on
# the held-out calibration split is required before prediction_service.py
# will expose ANY numeric score; otherwise the API returns the risk BAND
# ONLY (LOW/MODERATE/HIGH) and the UI must not render a number.
# 0.25 is the Brier score of "always predict the class base rate" for a
# perfectly balanced 3-class-ish problem -- a fitted calibrator must beat
# that meaningfully, not just tie it, to be considered informative.
CALIBRATION_BRIER_THRESHOLD = 0.20

# ASYMMETRIC MISCLASSIFICATION COST (spec: ordinal target + asymmetric cost).
# In screening, a missed HIGH (predicted LOW when truly HIGH) sends someone
# home untreated; a false MODERATE (predicted MODERATE when truly HIGH, or
# vice versa) costs at most one extra CHC visit. Rather than replacing the
# multiclass objective with a full ordinal formulation, this cost matrix is
# applied at EVALUATION time (training/evaluate.py) to compute a
# cost-weighted score alongside the confusion matrix -- accuracy alone
# treats a LOW/HIGH confusion identically to a LOW/MODERATE confusion,
# which is clinically backwards.
# Rows = true label, columns = predicted label, order matches RISK_LABELS.
MISCLASSIFICATION_COST_MATRIX = [
    # predicted:  LOW    MODERATE  HIGH
    [0.0, 1.0, 2.0],   # true LOW
    [1.0, 0.0, 1.0],   # true MODERATE
    [4.0, 2.0, 0.0],   # true HIGH -- predicting LOW when truly HIGH is the worst possible error
]

# SUBGROUP FAIRNESS DEPLOYMENT BLOCKER: any subgroup (age band, sex, site,
# BMI band, habitual-squatting status) whose sensitivity falls this many
# percentage points below the overall sensitivity is flagged as a
# deployment blocker in validation/subgroups.py -- must be investigated
# before shipping a model, not just noted and shipped anyway.
SUBGROUP_SENSITIVITY_DROP_BLOCKER_PP = 15

# Same idea for cross-site/cross-device generalization
# (validation/protocols.py's leave_one_site_out / leave_one_device_out).
SITE_OR_DEVICE_SENSITIVITY_DROP_BLOCKER_PP = 10
