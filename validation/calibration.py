"""
Calibration gate (spec: numeric score honesty).

XGBoost's raw softmax output is a probability-shaped number, not a
calibrated probability -- "risk score 62" implies precision the model does
not actually have unless a calibrator has been fit on a held-out split and
checked. This module is the ONLY place a calibrator is fit, saved, loaded,
or checked; backend/services/prediction_service.py calls
is_gate_passed()/load_calibrator() rather than doing any of this inline.

Fitting protocol:
  - Requires a CALIBRATION split, separate from both the training split and
    the final test split (three-way split, not two-way) -- calibrating and
    then evaluating on the same held-out data would leak information and
    make the reported Brier score overly optimistic.
  - Uses isotonic regression by default (non-parametric, more flexible);
    falls back to Platt scaling (a 1D logistic regression) for small
    calibration sets, where isotonic regression tends to overfit the
    handful of points it's given.
"""
import json
import os
import pickle

import numpy as np
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss

from config.model_config import CALIBRATION_BRIER_THRESHOLD

VALIDATION_DIR = os.path.dirname(os.path.abspath(__file__))
CALIBRATOR_PATH = os.path.join(VALIDATION_DIR, "models", "calibrator.pkl")
CALIBRATOR_META_PATH = os.path.join(VALIDATION_DIR, "models", "calibrator_meta.json")
REPORTS_DIR = os.path.join(VALIDATION_DIR, "reports")

# Below this many calibration points, isotonic regression tends to produce a
# degenerate step function that overfits -- use Platt scaling instead.
SMALL_N_THRESHOLD = 30


def fit_calibrator(confidence_scores, correct_flags, method: str = "auto"):
    """
    confidence_scores: array-like of the model's predicted-class probability
        (i.e. max(softmax output)) for each calibration-split example.
    correct_flags: array-like of 1/0, whether that prediction's class
        actually matched the true label.
    method: "isotonic", "platt", or "auto" (picks platt below SMALL_N_THRESHOLD).

    Returns a fitted calibrator object with a .predict(confidence) method
    mapping a raw confidence score to a calibrated probability of being
    correct. Does NOT save it -- call save_calibrator() separately so
    fitting and persisting are explicit, separate steps.
    """
    x = np.asarray(confidence_scores, dtype=float)
    y = np.asarray(correct_flags, dtype=float)
    if len(x) < 5:
        raise ValueError("Need at least 5 calibration examples to fit anything meaningful")

    if method == "auto":
        method = "platt" if len(x) < SMALL_N_THRESHOLD else "isotonic"

    if method == "isotonic":
        calibrator = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0)
        calibrator.fit(x, y)
    elif method == "platt":
        calibrator = LogisticRegression()
        calibrator.fit(x.reshape(-1, 1), y)
    else:
        raise ValueError(f"Unknown calibration method: {method}")

    calibrator._jointx_method = method  # noqa: SLF001 -- tag for save_calibrator/reporting
    return calibrator


def _predict_calibrated(calibrator, confidence_scores):
    x = np.asarray(confidence_scores, dtype=float)
    method = getattr(calibrator, "_jointx_method", "isotonic")
    if method == "platt":
        return calibrator.predict_proba(x.reshape(-1, 1))[:, 1]
    return calibrator.predict(x)


def compute_brier_score(calibrator, confidence_scores, correct_flags) -> float:
    """Lower is better; 0 is perfect, 0.25 is what a coin-flip-ish classifier scores."""
    calibrated = _predict_calibrated(calibrator, confidence_scores)
    return float(brier_score_loss(correct_flags, calibrated))


def is_gate_passed(brier_score: float) -> bool:
    return brier_score <= CALIBRATION_BRIER_THRESHOLD


def save_calibrator(calibrator, confidence_scores, correct_flags, n_calibration_samples: int = None):
    """
    Saves the fitted calibrator AND a metadata sidecar recording its Brier
    score and whether it passed the gate -- prediction_service.py reads the
    metadata (cheap) far more often than it would need to reload+re-score
    the calibrator itself.
    """
    os.makedirs(os.path.dirname(CALIBRATOR_PATH), exist_ok=True)
    brier = compute_brier_score(calibrator, confidence_scores, correct_flags)

    with open(CALIBRATOR_PATH, "wb") as f:
        pickle.dump(calibrator, f)

    meta = {
        "brier_score": brier,
        "gate_passed": is_gate_passed(brier),
        "threshold": CALIBRATION_BRIER_THRESHOLD,
        "method": getattr(calibrator, "_jointx_method", "unknown"),
        "n_calibration_samples": n_calibration_samples if n_calibration_samples is not None else len(confidence_scores),
    }
    with open(CALIBRATOR_META_PATH, "w") as f:
        json.dump(meta, f, indent=2)
    return meta


def load_calibrator_meta() -> dict:
    """
    Returns {"exists": False} if no calibrator has ever been fit, otherwise
    the saved metadata (brier_score, gate_passed, etc). This is the cheap
    check prediction_service.py uses on every prediction -- it does NOT
    load the pickled calibrator object unless a numeric score actually needs
    to be computed.
    """
    if not os.path.exists(CALIBRATOR_META_PATH):
        return {"exists": False}
    with open(CALIBRATOR_META_PATH) as f:
        meta = json.load(f)
    meta["exists"] = True
    return meta


def load_calibrator():
    if not os.path.exists(CALIBRATOR_PATH):
        raise FileNotFoundError("No fitted calibrator exists -- run fit_calibrator()+save_calibrator() first")
    with open(CALIBRATOR_PATH, "rb") as f:
        return pickle.load(f)


def calibrated_score(raw_confidence: float) -> float:
    """
    Converts one raw model confidence into a calibrated 0-100 score.
    Callers MUST check load_calibrator_meta()["gate_passed"] before calling
    this -- it does not check the gate itself, since the gate decision
    (show a number vs. band-only) belongs to the caller
    (backend/services/prediction_service.py), not to this low-level helper.
    """
    calibrator = load_calibrator()
    calibrated = _predict_calibrated(calibrator, [raw_confidence])[0]
    return round(float(calibrated) * 100, 1)


def plot_reliability_diagram(confidence_scores, correct_flags, output_path: str = None, n_bins: int = 10):
    """
    Saves a reliability diagram (predicted confidence bucket vs. actual
    fraction correct in that bucket) to validation/reports/. Requires
    matplotlib; if unavailable, this simply isn't called by the CLI report
    generator (see validation/run_calibration_report.py) -- it is not
    required for the gate itself to function.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    x = np.asarray(confidence_scores, dtype=float)
    y = np.asarray(correct_flags, dtype=float)
    bins = np.linspace(0, 1, n_bins + 1)
    bin_indices = np.digitize(x, bins) - 1
    bin_indices = np.clip(bin_indices, 0, n_bins - 1)

    bin_confidence, bin_accuracy, bin_counts = [], [], []
    for b in range(n_bins):
        mask = bin_indices == b
        if mask.sum() == 0:
            continue
        bin_confidence.append(x[mask].mean())
        bin_accuracy.append(y[mask].mean())
        bin_counts.append(int(mask.sum()))

    fig, ax = plt.subplots(figsize=(5, 5))
    ax.plot([0, 1], [0, 1], linestyle="--", color="gray", label="Perfect calibration")
    ax.scatter(bin_confidence, bin_accuracy, s=[c * 5 for c in bin_counts], label="Observed (size = bin count)")
    ax.set_xlabel("Predicted confidence")
    ax.set_ylabel("Observed fraction correct")
    ax.set_title("Reliability Diagram")
    ax.legend()
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)

    os.makedirs(REPORTS_DIR, exist_ok=True)
    output_path = output_path or os.path.join(REPORTS_DIR, "reliability_diagram.png")
    fig.savefig(output_path, dpi=120, bbox_inches="tight")
    plt.close(fig)
    return output_path
