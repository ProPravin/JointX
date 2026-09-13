"""
Exports a labelled raw_dataset.csv straight out of the live JointX database
(data/jointx.db by default), for use as the input to training/preprocessing.py.

For each screening, this reuses the EXACT feature dict already computed and
stored by fusion/fusion.py at screening time (fused_features.feature_json) --
it does not recompute features here -- so the exported columns are guaranteed
to match fusion/feature_schema.py's current 25-feature schema (SCHEMA_VERSION).

A screening is only exported if it has:
  1. A fused_features row matching the CURRENT schema version (an older/newer
     schema version means the feature set has since changed shape).
  2. A resolvable ground-truth risk_label:
       - a clinician_label recorded on the healthcare_reviews row, OR
       - agrees_with_model == 1, in which case the model's own predictions.risk_label
         is trusted as the confirmed label.
     A screening reviewed as "disagree" with no clinician_label has no
     resolvable ground truth and is skipped (see review_service.py, which
     requires clinician_label whenever agrees_with_model is 0 going forward --
     older reviews recorded before that requirement existed may still lack one).
  3. is_demo == 0 (simulated data is excluded by default; pass --include-demo
     to include it anyway, e.g. to sanity-check the pipeline mechanics).

Usage:
    python training/export_dataset.py --output training/datasets/raw_dataset.csv
"""
import argparse
import sqlite3
import sys
from collections import Counter

import pandas as pd

sys.path.insert(0, __file__.rsplit("training", 1)[0])  # allow running as a script

from fusion.feature_schema import FEATURE_NAMES, SCHEMA_VERSION  # noqa: E402
from backend.utils.helpers import from_json  # noqa: E402
from config.settings import Config  # noqa: E402


def _row_factory(cursor, row):
    return {col[0]: row[idx] for idx, col in enumerate(cursor.description)}


def export_dataset(db_path: str, include_demo: bool = False) -> tuple:
    """Returns (DataFrame, Counter of skip reasons)."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = _row_factory
    cur = conn.cursor()

    cur.execute("SELECT * FROM screenings")
    screenings = cur.fetchall()

    rows = []
    skipped = Counter()

    for screening in screenings:
        screening_id = screening["id"]

        if not include_demo and screening["is_demo"]:
            skipped["demo_data"] += 1
            continue

        cur.execute("SELECT * FROM fused_features WHERE screening_id = ?", (screening_id,))
        fused_row = cur.fetchone()
        if not fused_row:
            skipped["no_fused_features"] += 1
            continue
        if fused_row["schema_version"] != SCHEMA_VERSION:
            skipped["schema_version_mismatch"] += 1
            continue

        fused = from_json(fused_row["feature_json"])
        features = (fused or {}).get("features")
        if not features:
            skipped["unreadable_feature_json"] += 1
            continue

        cur.execute("SELECT * FROM healthcare_reviews WHERE screening_id = ?", (screening_id,))
        review = cur.fetchone()

        risk_label = None
        if review and review.get("clinician_label"):
            risk_label = review["clinician_label"]
        elif review and review.get("agrees_with_model") == 1:
            cur.execute("SELECT * FROM predictions WHERE screening_id = ?", (screening_id,))
            prediction = cur.fetchone()
            if prediction:
                risk_label = prediction["risk_label"]

        if not risk_label:
            skipped["no_ground_truth_label"] += 1
            continue

        row = {"subject_id": screening["patient_id"], "screening_id": screening_id, "risk_label": risk_label}
        row.update({name: features.get(name) for name in FEATURE_NAMES})
        rows.append(row)

    conn.close()

    columns = ["subject_id", "screening_id", "risk_label"] + FEATURE_NAMES
    df = pd.DataFrame(rows, columns=columns)
    return df, skipped


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=Config.DATABASE_PATH, help="Path to jointx.db (default: configured DATABASE_PATH)")
    parser.add_argument("--output", required=True, help="Output CSV path, e.g. training/datasets/raw_dataset.csv")
    parser.add_argument("--include-demo", action="store_true", help="Include is_demo screenings (excluded by default)")
    args = parser.parse_args()

    df, skipped = export_dataset(args.db, include_demo=args.include_demo)
    df.to_csv(args.output, index=False)

    print(f"Exported {len(df)} labelled screening(s) from {df['subject_id'].nunique()} subject(s) to {args.output}")
    if skipped:
        print("Skipped:")
        for reason, count in skipped.items():
            print(f"  {reason}: {count}")
    if len(df) == 0:
        print(
            "\nNo rows exported. Nothing to train on yet -- this is expected until real "
            "screenings have been run through the full pipeline (gait + IMU + functional "
            "tests + fuse) AND reviewed by a healthcare worker with either agreement or a "
            "clinician_label."
        )


if __name__ == "__main__":
    if len(sys.argv) == 1:
        print(__doc__)
        sys.exit(0)
    main()
