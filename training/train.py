"""
Trains an XGBoost multiclass model on the (subject-independent) training
split and saves it to ml/models/. Does NOT evaluate or report accuracy —
that is evaluate.py's job, run on the held-out test set only.

Usage:
    python training/train.py --train training/datasets/train.csv \
        --output ml/models/jointx_xgb_model.json
"""
import argparse
import sys

import pandas as pd
import xgboost as xgb

from fusion.feature_schema import FEATURE_NAMES
from config.model_config import XGBOOST_TRAIN_PARAMS


def train_model(train_df: pd.DataFrame, params: dict = None, num_boost_round: int = 100):
    """
    Missing feature values are passed to XGBoost as NaN, NOT 0.0 (spec:
    Data Integrity #A2). A missing cadence reading, for example, means
    "gait was not captured" -- coercing it to 0.0 tells the model "this
    patient did not walk at all", which is a severe-disease pattern, not a
    hardware-failure pattern. XGBoost natively learns a per-split default
    direction for missing values, so no imputation is needed or wanted here.
    """
    params = params or XGBOOST_TRAIN_PARAMS
    X = train_df[FEATURE_NAMES].astype(float).values
    y = train_df["risk_label_idx"].values
    weights = train_df["sample_weight"].astype(float).values if "sample_weight" in train_df.columns else None

    dtrain = xgb.DMatrix(X, label=y, weight=weights, feature_names=FEATURE_NAMES, missing=float("nan"))
    booster = xgb.train(params, dtrain, num_boost_round=num_boost_round)
    return booster


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--train", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--rounds", type=int, default=100)
    args = parser.parse_args()

    train_df = pd.read_csv(args.train)
    booster = train_model(train_df, num_boost_round=args.rounds)
    booster.save_model(args.output)
    print(f"Model saved to {args.output}")
    print(
        "Reminder: run training/evaluate.py on a held-out subject-independent "
        "test set before treating this model as anything other than a prototype."
    )


if __name__ == "__main__":
    if len(sys.argv) == 1:
        print(__doc__)
        sys.exit(0)
    main()
