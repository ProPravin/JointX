"""
Builds the final training feature matrix (X) and labels (y) from a cleaned
dataset, using the SAME column order as fusion/feature_schema.py so training
and inference are guaranteed consistent.

Usage:
    python training/feature_engineering.py --input training/datasets/clean_dataset.csv \
        --output training/datasets/features.csv
"""
import argparse
import sys

import pandas as pd

from fusion.feature_schema import FEATURE_NAMES
from config.model_config import RISK_LABELS


def build_feature_table(df: pd.DataFrame) -> pd.DataFrame:
    # label_source/sample_weight/is_blinded come from export_dataset.py (spec:
    # Data Integrity #A1) and must survive into the final feature table so
    # train.py can weight samples and validation/protocols.py can filter to
    # blinded-only rows for the test split. Tolerate older datasets exported
    # before these columns existed (sample_weight defaults to 1.0, unweighted).
    provenance_cols = [c for c in ("label_source", "sample_weight", "is_blinded") if c in df.columns]
    cols = ["subject_id"] + FEATURE_NAMES + ["risk_label"] + provenance_cols
    out = df[cols].copy()
    if "sample_weight" not in out.columns:
        out["sample_weight"] = 1.0
    out["risk_label_idx"] = out["risk_label"].apply(
        lambda v: RISK_LABELS.index(v) if v in RISK_LABELS else None
    )
    out = out.dropna(subset=["risk_label_idx"])
    out["risk_label_idx"] = out["risk_label_idx"].astype(int)
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    df = pd.read_csv(args.input)
    features = build_feature_table(df)
    features.to_csv(args.output, index=False)
    print(f"Feature table written to {args.output} ({len(features)} rows)")


if __name__ == "__main__":
    if len(sys.argv) == 1:
        print(__doc__)
        sys.exit(0)
    main()
