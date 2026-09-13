"""
Evaluates a trained model on the held-out (subject-independent) test set.
Computes sensitivity, specificity, precision, recall, F1, and ROC-AUC per
class, using ONLY real predictions on real held-out data (spec section 24).
Never hard-code or fabricate these numbers elsewhere in the app.

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
from config.model_config import RISK_LABELS


def evaluate(model_path: str, test_df: pd.DataFrame) -> dict:
    booster = xgb.Booster()
    booster.load_model(model_path)

    X = test_df[FEATURE_NAMES].fillna(0.0).values
    y_true = test_df["risk_label_idx"].values

    dtest = xgb.DMatrix(X, feature_names=FEATURE_NAMES)
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

    return {
        "classification_report": report,
        "confusion_matrix": cm.tolist(),
        "roc_auc_ovr": auc,
        "n_test_samples": len(test_df),
        "n_test_subjects": int(test_df["subject_id"].nunique()),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True)
    parser.add_argument("--test", required=True)
    args = parser.parse_args()

    test_df = pd.read_csv(args.test)
    results = evaluate(args.model, test_df)

    print(f"Evaluated on {results['n_test_samples']} samples "
          f"({results['n_test_subjects']} subjects)")
    print("Confusion matrix (rows=true, cols=pred):")
    print(np.array(results["confusion_matrix"]))
    print(f"ROC-AUC (OVR): {results['roc_auc_ovr']}")
    for label in RISK_LABELS:
        stats = results["classification_report"].get(label, {})
        print(
            f"{label}: precision={stats.get('precision'):.3f} "
            f"recall={stats.get('recall'):.3f} f1={stats.get('f1-score'):.3f}"
            if stats else f"{label}: no samples in test set"
        )


if __name__ == "__main__":
    if len(sys.argv) == 1:
        print(__doc__)
        sys.exit(0)
    main()
