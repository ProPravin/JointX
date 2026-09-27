"""
Evaluates a trained model on the held-out (subject-independent) test set.
Computes sensitivity, specificity, precision, recall, F1, and ROC-AUC per
class, using ONLY real predictions on real held-out data (spec section 24).
Never hard-code or fabricate these numbers elsewhere in the app.

CAVEAT PRINTED EVERY RUN, DELIBERATELY: accuracy alone is actively
misleading on an imbalanced screening population (most people are LOW
risk) -- a model that always predicts LOW can score high "accuracy" while
missing every HIGH-risk case, which is the exact failure mode a screening
tool must not have. This is why accuracy is never printed here at all;
only per-class sensitivity/specificity/precision/recall and the full
confusion matrix are reported.

Also applies (spec: honest evaluation for small N):
  - MINIMUM-N GATE: below config/model_config.py's thresholds, output is
    prefixed "STATISTICALLY UNRELIABLE -- N TOO SMALL" and
    backend/services/model_status_service.py refuses to serve these numbers.
  - Bootstrap 95% CIs on sensitivity/specificity -- never a bare point
    estimate.
  - A cost-weighted score using the asymmetric misclassification cost
    matrix (a missed HIGH is far worse than a false MODERATE).

Usage:
    python training/evaluate.py --model ml/models/jointx_xgb_model.json \
        --test training/datasets/test.csv
"""
import argparse
import sys

import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.metrics import (
    classification_report,
    confusion_matrix,
    roc_auc_score,
)

from fusion.feature_schema import FEATURE_NAMES
from config.model_config import RISK_LABELS, MISCLASSIFICATION_COST_MATRIX
from validation.protocols import minimum_n_gate, bootstrap_ci
from validation.subgroups import sensitivity_for_class, specificity_for_class


def cost_weighted_score(y_true, y_pred) -> float:
    """
    Mean misclassification cost per example using
    config/model_config.py's MISCLASSIFICATION_COST_MATRIX (0 for a correct
    call). Lower is better; 0 would mean every prediction was correct.
    """
    y_true, y_pred = np.asarray(y_true), np.asarray(y_pred)
    costs = [MISCLASSIFICATION_COST_MATRIX[t][p] for t, p in zip(y_true, y_pred)]
    return float(np.mean(costs))


def evaluate(model_path: str, test_df: pd.DataFrame) -> dict:
    booster = xgb.Booster()
    booster.load_model(model_path)

    # Missing values stay NaN through evaluation too (spec: Data Integrity
    # #A2) -- filling with 0.0 here would silently score refused-quality
    # captures as if every sensor read cleanly, corrupting the reported metrics.
    X = test_df[FEATURE_NAMES].astype(float).values
    y_true = test_df["risk_label_idx"].values

    dtest = xgb.DMatrix(X, feature_names=FEATURE_NAMES, missing=float("nan"))
    probs = booster.predict(dtest)  # shape (n, n_classes)
    y_pred = np.argmax(probs, axis=1)

    report = classification_report(
        y_true, y_pred, target_names=RISK_LABELS, output_dict=True, zero_division=0
    )
    cm = confusion_matrix(y_true, y_pred, labels=list(range(len(RISK_LABELS))))

    try:
        auc = roc_auc_score(y_true, probs, multi_class="ovr")
    except ValueError:
        auc = None  # e.g. a class missing from the (small) test set

    # Bootstrap CIs on per-class sensitivity/specificity -- resamples ROWS
    # (not subjects) from the already-computed (y_true, y_pred) pairs. This
    # captures sampling variability of the metric given this exact test set;
    # it does NOT capture subject-level correlation the way a repeated
    # GroupKFold over the full dataset would (see validation/protocols.py's
    # repeated_group_kfold for that, run separately/upstream of this script).
    rng = np.random.default_rng(42)
    n = len(y_true)
    per_class_ci = {}
    for idx, label in enumerate(RISK_LABELS):
        sens_samples, spec_samples = [], []
        for _ in range(1000):
            sample_idx = rng.choice(n, size=n, replace=True)
            sens_samples.append(sensitivity_for_class(y_true[sample_idx], y_pred[sample_idx], idx))
            spec_samples.append(specificity_for_class(y_true[sample_idx], y_pred[sample_idx], idx))
        per_class_ci[label] = {
            "sensitivity_ci": bootstrap_ci(sens_samples),
            "specificity_ci": bootstrap_ci(spec_samples),
        }

    n_gate = minimum_n_gate(test_df, subject_col="subject_id", label_col="risk_label")

    return {
        "classification_report": report,
        "confusion_matrix": cm.tolist(),
        "roc_auc_ovr": auc,
        "n_test_samples": len(test_df),
        "n_test_subjects": int(test_df["subject_id"].nunique()),
        "cost_weighted_score": cost_weighted_score(y_true, y_pred),
        "per_class_bootstrap_ci": per_class_ci,
        "minimum_n_gate": n_gate,
        "accuracy_deliberately_not_reported": (
            "Accuracy alone is misleading on an imbalanced screening population; "
            "see per-class sensitivity/specificity and the confusion matrix instead."
        ),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True)
    parser.add_argument("--test", required=True)
    args = parser.parse_args()

    test_df = pd.read_csv(args.test)
    results = evaluate(args.model, test_df)

    if not results["minimum_n_gate"]["passed"]:
        print("*** STATISTICALLY UNRELIABLE — N TOO SMALL ***")
        print(f"    {results['minimum_n_gate']['reason']}")
        print("    The numbers below are printed for transparency but must NOT be")
        print("    reported as a performance claim or served to the dashboard.\n")

    print(f"Evaluated on {results['n_test_samples']} samples "
          f"({results['n_test_subjects']} subjects)")
    print("Confusion matrix (rows=true, cols=pred):")
    print(np.array(results["confusion_matrix"]))
    print(f"ROC-AUC (OVR): {results['roc_auc_ovr']}")
    print(f"Cost-weighted misclassification score (lower is better, 0=perfect): {results['cost_weighted_score']:.3f}")
    print(f"\nNOTE: {results['accuracy_deliberately_not_reported']}\n")

    for label in RISK_LABELS:
        stats = results["classification_report"].get(label, {})
        ci = results["per_class_bootstrap_ci"].get(label, {})
        if stats:
            sens_ci = ci.get("sensitivity_ci", {})
            spec_ci = ci.get("specificity_ci", {})
            print(
                f"{label}: precision={stats.get('precision'):.3f} "
                f"recall={stats.get('recall'):.3f} f1={stats.get('f1-score'):.3f}"
            )
            if sens_ci.get("point_estimate") is not None:
                print(f"        sensitivity 95% CI: [{sens_ci['ci_low']:.3f}, {sens_ci['ci_high']:.3f}]")
            if spec_ci.get("point_estimate") is not None:
                print(f"        specificity 95% CI: [{spec_ci['ci_low']:.3f}, {spec_ci['ci_high']:.3f}]")
        else:
            print(f"{label}: no samples in test set")


if __name__ == "__main__":
    if len(sys.argv) == 1:
        print(__doc__)
        sys.exit(0)
    main()
