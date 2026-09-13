"""
Splits a feature table into train/test sets by subject_id, so that no
patient's data appears in both sets (prevents data leakage — spec section 24).

Usage:
    python training/split.py --input training/datasets/features.csv \
        --train-output training/datasets/train.csv \
        --test-output training/datasets/test.csv \
        --test-fraction 0.2
"""
import argparse
import sys

import numpy as np
import pandas as pd


def subject_independent_split(df: pd.DataFrame, test_fraction: float = 0.2, seed: int = 42):
    subjects = df["subject_id"].unique()
    rng = np.random.default_rng(seed)
    rng.shuffle(subjects)

    n_test = max(1, int(len(subjects) * test_fraction))
    test_subjects = set(subjects[:n_test])
    train_subjects = set(subjects[n_test:])

    train_df = df[df["subject_id"].isin(train_subjects)].copy()
    test_df = df[df["subject_id"].isin(test_subjects)].copy()

    overlap = train_subjects & test_subjects
    assert not overlap, f"Subject leakage detected: {overlap}"

    return train_df, test_df


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--train-output", required=True)
    parser.add_argument("--test-output", required=True)
    parser.add_argument("--test-fraction", type=float, default=0.2)
    args = parser.parse_args()

    df = pd.read_csv(args.input)
    train_df, test_df = subject_independent_split(df, args.test_fraction)
    train_df.to_csv(args.train_output, index=False)
    test_df.to_csv(args.test_output, index=False)
    print(f"Train: {len(train_df)} rows ({train_df['subject_id'].nunique()} subjects)")
    print(f"Test:  {len(test_df)} rows ({test_df['subject_id'].nunique()} subjects)")


if __name__ == "__main__":
    if len(sys.argv) == 1:
        print(__doc__)
        sys.exit(0)
    main()
