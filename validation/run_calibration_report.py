"""
Fits a calibrator on a held-out CALIBRATION split (separate from both the
training split and the final test split -- spec: numeric score honesty) and
saves it, its metadata, and a reliability diagram to validation/.

Usage:
    python validation/run_calibration_report.py \
        --model ml/models/jointx_xgb_model.json \
        --calibration training/datasets/calibration.csv

The calibration CSV must have the same columns as train.csv/test.csv
(FEATURE_NAMES + risk_label_idx + subject_id) -- carve it out of your full
dataset as a THIRD split, e.g. by re-running training/split.py's
subject_independent_split() on the training portion to peel off ~15-20% as
a calibration set before fitting the final model on what remains.

Until this has actually been run on real data with a passing Brier score,
backend/services/prediction_service.py will correctly withhold any numeric
score from every prediction and show only the LOW/MODERATE/HIGH band.
"""
import argparse
import sys
import os

import numpy as np
import pandas as pd
import xgboost as xgb

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fusion.feature_schema import FEATURE_NAMES  # noqa: E402
from validation.calibration import fit_calibrator, save_calibrator, plot_reliability_diagram  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--model", required=True)
    parser.add_argument("--calibration", required=True, help="Path to the calibration-split CSV")
    parser.add_argument("--method", default="auto", choices=["auto", "isotonic", "platt"])
    args = parser.parse_args()

    calib_df = pd.read_csv(args.calibration)
    booster = xgb.Booster()
    booster.load_model(args.model)

    X = calib_df[FEATURE_NAMES].astype(float).values
    y_true = calib_df["risk_label_idx"].values
    dcalib = xgb.DMatrix(X, feature_names=FEATURE_NAMES, missing=float("nan"))
    probs = booster.predict(dcalib)

    confidence = probs.max(axis=1)
    predicted_class = np.argmax(probs, axis=1)
    correct = (predicted_class == y_true).astype(int)

    print(f"Fitting calibrator on {len(calib_df)} calibration examples ({calib_df['subject_id'].nunique()} subjects)...")
    calibrator = fit_calibrator(confidence, correct, method=args.method)
    meta = save_calibrator(calibrator, confidence, correct, n_calibration_samples=len(calib_df))

    print(f"Method: {meta['method']}")
    print(f"Brier score: {meta['brier_score']:.4f} (threshold: {meta['threshold']})")
    print(f"Gate passed: {meta['gate_passed']}")

    try:
        diagram_path = plot_reliability_diagram(confidence, correct)
        print(f"Reliability diagram written to {diagram_path}")
    except ImportError:
        print("matplotlib not available -- skipped reliability diagram (Brier score/gate result above still valid)")

    if meta["gate_passed"]:
        print("\nNumeric scores will now be shown by prediction_service.py.")
    else:
        print("\nGate NOT passed -- prediction_service.py will continue to show BAND ONLY (no numeric score).")


if __name__ == "__main__":
    if len(sys.argv) == 1:
        print(__doc__)
        sys.exit(0)
    main()
