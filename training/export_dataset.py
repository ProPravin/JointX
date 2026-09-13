"""
Exports a labelled raw_dataset.csv straight out of the live JointX database
(data/jointx.db by default), for use as the input to training/preprocessing.py.

For each screening, this reuses the EXACT feature dict already computed and
stored by fusion/fusion.py at screening time (fused_features.feature_json) --
it does not recompute features here -- so the exported columns are guaranteed
to match fusion/feature_schema.py's current schema (SCHEMA_VERSION).

LABEL INTEGRITY (spec: Data Integrity #A1)
-------------------------------------------
Ground truth comes from healthcare_reviews.clinician_label, but that column
alone does not say how trustworthy the label is. label_source distinguishes:

  kl_grade              radiograph-confirmed Kellgren-Lawrence grade -- strongest
  acr_clinical          ACR clinical criteria checklist -- strong
  clinician_impression  reviewer's own clinical judgement, no imaging/criteria -- moderate
  model_confirmed       reviewer just clicked "agree" with the model's own output

model_confirmed rows are EXCLUDED from training and test sets by default:
using them would train the model on its own predictions, which is
self-reinforcing and makes every downstream accuracy number meaningless.
--include-model-confirmed exists ONLY to exercise pipeline mechanics (e.g. CI
with too little real data); when used, the output CSV and console report are
stamped "CONTAMINATED — NOT FOR REPORTING" so nobody mistakes it for a real
evaluation.

Each exported row also carries a sample_weight (kl_grade=1.0, acr_clinical=0.8,
clinician_impression=0.5) for training/train.py to pass to xgb.DMatrix(weight=).

Only a BLINDED label (reviewer_label_blind recorded before prediction_revealed_at)
is eligible to serve as a gold-standard TEST label -- see training/split.py /
validation/protocols.py, which must filter on is_blinded before building the
test split. This script reports the blinded fraction but does not itself
split train/test.

A screening is only exported if it has:
  1. A fused_features row matching the CURRENT schema version.
  2. A healthcare_reviews row with both clinician_label and label_source set.
  3. is_demo == 0 (simulated data is excluded by default; pass --include-demo
     to include it anyway, e.g. to sanity-check pipeline mechanics).

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

SAMPLE_WEIGHTS = {
    "kl_grade": 1.0,
    "acr_clinical": 0.8,
    "clinician_impression": 0.5,
    # Only reachable with --include-model-confirmed; deliberately low so it
    # can never dominate a mixed-source training run even if included.
    "model_confirmed": 0.1,
}

AUTOMATION_BIAS_THRESHOLD = 0.85


def _row_factory(cursor, row):
    return {col[0]: row[idx] for idx, col in enumerate(cursor.description)}


def export_dataset(db_path: str, include_demo: bool = False, include_model_confirmed: bool = False) -> tuple:
    """Returns (DataFrame, Counter of skip reasons, stats dict)."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = _row_factory
    cur = conn.cursor()

    cur.execute("SELECT * FROM screenings")
    screenings = cur.fetchall()

    rows = []
    skipped = Counter()
    label_source_counts = Counter()
    blinded_count = 0
    agreement_total = 0
    agreement_yes = 0

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

        if not review or not review.get("clinician_label") or not review.get("label_source"):
            skipped["no_ground_truth_label"] += 1
            continue

        # Automation-bias / blinding stats are computed over EVERY reviewed
        # screening reaching this point, regardless of whether it is
        # ultimately included in the exported CSV -- these are diagnostics
        # about review quality, not about the training set itself.
        if review.get("agrees_with_model") is not None:
            agreement_total += 1
            if review["agrees_with_model"] == 1:
                agreement_yes += 1
        is_blinded = bool(review.get("reviewer_label_blind") and review.get("prediction_revealed_at"))
        if is_blinded:
            blinded_count += 1

        label_source = review["label_source"]
        label_source_counts[label_source] += 1

        if label_source == "model_confirmed" and not include_model_confirmed:
            skipped["model_confirmed_excluded"] += 1
            continue

        row = {
            "subject_id": screening["patient_id"],
            "screening_id": screening_id,
            "risk_label": review["clinician_label"],
            "label_source": label_source,
            "sample_weight": SAMPLE_WEIGHTS.get(label_source, 0.0),
            "is_blinded": int(is_blinded),
        }
        row.update({name: features.get(name) for name in FEATURE_NAMES})
        rows.append(row)

    conn.close()

    columns = ["subject_id", "screening_id", "risk_label", "label_source", "sample_weight", "is_blinded"] + FEATURE_NAMES
    df = pd.DataFrame(rows, columns=columns)

    stats = {
        "label_source_counts": label_source_counts,
        "blinded_count": blinded_count,
        "blinded_total_reviewed": agreement_total,  # rows with agrees_with_model set is our denominator for "reviewed"
        "agreement_total": agreement_total,
        "agreement_yes": agreement_yes,
    }
    return df, skipped, stats


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db", default=Config.DATABASE_PATH, help="Path to jointx.db (default: configured DATABASE_PATH)")
    parser.add_argument("--output", required=True, help="Output CSV path, e.g. training/datasets/raw_dataset.csv")
    parser.add_argument("--include-demo", action="store_true", help="Include is_demo screenings (excluded by default)")
    parser.add_argument(
        "--include-model-confirmed",
        action="store_true",
        help="Include model_confirmed rows. PIPELINE-MECHANICS TESTING ONLY -- "
        "output is stamped CONTAMINATED and must never be used for a reported metric.",
    )
    args = parser.parse_args()

    df, skipped, stats = export_dataset(
        args.db, include_demo=args.include_demo, include_model_confirmed=args.include_model_confirmed
    )

    if args.include_model_confirmed:
        contamination_notice = (
            "# CONTAMINATED — NOT FOR REPORTING "
            "(built with --include-model-confirmed; contains rows where the "
            "model's own output was used as ground truth)\n"
        )
        with open(args.output, "w", newline="") as f:
            f.write(contamination_notice)
            df.to_csv(f, index=False)
    else:
        df.to_csv(args.output, index=False)

    print(f"Exported {len(df)} labelled screening(s) from {df['subject_id'].nunique()} subject(s) to {args.output}")
    if args.include_model_confirmed:
        print("*** OUTPUT IS CONTAMINATED — NOT FOR REPORTING (--include-model-confirmed was used) ***")

    if skipped:
        print("Skipped:")
        for reason, count in skipped.items():
            print(f"  {reason}: {count}")

    print("\nLabel counts by source (all reviewed screenings, before exclusion):")
    total_labelled = sum(stats["label_source_counts"].values())
    for source, count in stats["label_source_counts"].items():
        pct = (count / total_labelled * 100) if total_labelled else 0.0
        print(f"  {source}: {count} ({pct:.1f}%)")

    if stats["agreement_total"]:
        blinded_pct = stats["blinded_count"] / stats["agreement_total"] * 100
        agreement_rate = stats["agreement_yes"] / stats["agreement_total"]
        print(f"\n% of reviews that were properly blinded: {blinded_pct:.1f}% ({stats['blinded_count']}/{stats['agreement_total']})")
        print(f"Reviewer-model agreement rate: {agreement_rate * 100:.1f}% ({stats['agreement_yes']}/{stats['agreement_total']})")
        if agreement_rate > AUTOMATION_BIAS_THRESHOLD:
            print(
                f"  WARNING: agreement rate exceeds {AUTOMATION_BIAS_THRESHOLD * 100:.0f}% — this is a red flag for "
                "automation bias (reviewers rubber-stamping the model rather than forming an independent judgement). "
                "Investigate the blinded-review workflow before trusting these labels."
            )
    else:
        print("\nNo reviewed screenings with agrees_with_model set — cannot compute blinding/agreement stats yet.")

    if len(df) == 0:
        print(
            "\nNo rows exported. Nothing to train on yet -- this is expected until real "
            "screenings have been run through the full pipeline (gait + IMU + functional "
            "tests + fuse), predicted, and reviewed through the blinded review workflow "
            "with a label_source other than model_confirmed."
        )


if __name__ == "__main__":
    if len(sys.argv) == 1:
        print(__doc__)
        sys.exit(0)
    main()
