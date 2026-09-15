"""
PIPELINE SMOKE TEST ONLY -- NOT A PERFORMANCE CLAIM (spec: P2 #8).

Generates synthetic feature/label data and runs it through the entire real
training pipeline (preprocessing -> feature_engineering -> split -> train ->
evaluate) purely to prove the pipeline's MECHANICS work: correct shapes,
correct handling of NaN missing values and sample weights, no crashes,
`evaluate.py` produces a well-formed report. It proves nothing whatsoever
about real-world model accuracy, because the data is synthetic.

Every artefact this script writes is stamped
"SYNTHETIC — PIPELINE VALIDATION ONLY, NOT A PERFORMANCE CLAIM" in three
places: the output filename, the JSON contents, and the printed summary.

CRITICAL: this script writes its trained model to training/synthetic_only/,
a path ml/model_loader.py NEVER reads from (it only reads Config.MODEL_PATH,
which defaults to ml/models/). A synthetic-trained model must never be
loadable by the running app -- see docs/MODEL_STATUS.md.

Usage:
    python training/pipeline_smoke_test.py
"""
import json
import os
import sys
from datetime import datetime, timezone

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fusion.feature_schema import FEATURE_NAMES  # noqa: E402
from config.model_config import RISK_LABELS  # noqa: E402
from training.preprocessing import clean_dataset  # noqa: E402
from training.feature_engineering import build_feature_table  # noqa: E402
from training.split import subject_independent_split  # noqa: E402
from training.train import train_model  # noqa: E402
from training.evaluate import evaluate  # noqa: E402

STAMP = "SYNTHETIC — PIPELINE VALIDATION ONLY, NOT A PERFORMANCE CLAIM"
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "synthetic_only")


def generate_synthetic_dataset(n_subjects: int = 60, seed: int = 42) -> pd.DataFrame:
    """
    Synthetic rows shaped exactly like a real export_dataset.py output --
    same columns, same label_source vocabulary, real feature-value ranges --
    but with randomly generated feature values and labels. There is no
    relationship between features and labels beyond what random chance
    produces, deliberately, so nobody could mistake resulting "accuracy" for
    a real signal.
    """
    rng = np.random.default_rng(seed)
    rows = []
    for subject_id in range(1, n_subjects + 1):
        row = {
            "subject_id": subject_id,
            "screening_id": subject_id,
            "risk_label": rng.choice(RISK_LABELS),
            "label_source": rng.choice(["kl_grade", "acr_clinical", "clinician_impression"]),
            "sample_weight": rng.choice([1.0, 0.8, 0.5]),
            "is_blinded": int(rng.random() > 0.3),
        }
        for name in FEATURE_NAMES:
            # ~10% missing, matching real-world capture-failure rates, to
            # exercise the NaN path through the whole pipeline for real.
            row[name] = np.nan if rng.random() < 0.1 else float(rng.uniform(0, 1) * 50)
        rows.append(row)
    return pd.DataFrame(rows)


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print(f"*** {STAMP} ***\n")

    raw_df = generate_synthetic_dataset()
    print(f"Generated {len(raw_df)} synthetic rows across {raw_df['subject_id'].nunique()} synthetic subjects.")

    clean_df = clean_dataset(raw_df)
    feature_df = build_feature_table(clean_df)
    train_df, test_df = subject_independent_split(feature_df, test_fraction=0.25, seed=42)
    print(f"Train: {len(train_df)} rows, Test: {len(test_df)} rows (subject-independent split verified).")

    booster = train_model(train_df, num_boost_round=20)

    model_path = os.path.join(OUTPUT_DIR, "SYNTHETIC_pipeline_smoke_test_model.json")
    booster.save_model(model_path)
    print(f"Synthetic model saved to {model_path} (NEVER read by ml/model_loader.py).")

    results = evaluate(model_path, test_df)
    results["synthetic"] = True
    results["stamp"] = STAMP
    results["generated_at"] = datetime.now(timezone.utc).isoformat()

    results_path = os.path.join(OUTPUT_DIR, "SYNTHETIC_pipeline_smoke_test_results.json")
    with open(results_path, "w") as f:
        json.dump(results, f, indent=2, default=str)

    print(f"\n{STAMP}")
    print(f"Results written to {results_path}")
    print(f"Confusion matrix shape: {len(results['confusion_matrix'])}x{len(results['confusion_matrix'][0])}")
    print("\nThis proves the pipeline runs end-to-end without crashing. It proves NOTHING about")
    print("real-world accuracy -- the labels are random and bear no relationship to the features.")
    print("See docs/MODEL_STATUS.md for what has to happen before a real model can exist.")


if __name__ == "__main__":
    main()
