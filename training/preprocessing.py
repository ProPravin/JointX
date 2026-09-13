"""
Cleans a raw labelled training dataset: drops rows with missing labels,
coerces feature columns to numeric, clips using the same bounds inference
will use (fusion/preprocessing.py) so train/inference distributions match.

Usage:
    python training/preprocessing.py --input training/datasets/raw_dataset.csv \
        --output training/datasets/clean_dataset.csv
"""
import argparse
import sys

import pandas as pd

from fusion.feature_schema import FEATURE_NAMES
from fusion.preprocessing import CLIP_BOUNDS


def clean_dataset(df: pd.DataFrame) -> pd.DataFrame:
    required_cols = set(FEATURE_NAMES) | {"subject_id", "risk_label"}
    missing_cols = required_cols - set(df.columns)
    if missing_cols:
        raise ValueError(f"Dataset is missing required columns: {missing_cols}")

    df = df.dropna(subset=["risk_label", "subject_id"]).copy()

    for col in FEATURE_NAMES:
        df[col] = pd.to_numeric(df[col], errors="coerce")
        lo, hi = CLIP_BOUNDS.get(col, (None, None))
        if lo is not None:
            df[col] = df[col].clip(lower=lo, upper=hi)

    df = df.dropna(subset=FEATURE_NAMES, how="all")
    return df


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    df = pd.read_csv(args.input)
    clean = clean_dataset(df)
    clean.to_csv(args.output, index=False)
    print(f"Cleaned dataset written to {args.output} ({len(clean)} rows)")


if __name__ == "__main__":
    if len(sys.argv) == 1:
        print(__doc__)
        sys.exit(0)
    main()
