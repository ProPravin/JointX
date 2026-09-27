"""Cost-weighted score, per-class bootstrap CIs, and the minimum-N gate inside evaluate.py."""
import os
import tempfile

from training.evaluate import evaluate, cost_weighted_score
from training.pipeline_smoke_test import generate_synthetic_dataset
from training.preprocessing import clean_dataset
from training.feature_engineering import build_feature_table
from training.split import subject_independent_split
from training.train import train_model


def test_cost_weighted_score_zero_when_all_correct():
    y_true = [0, 1, 2, 0, 1, 2]
    y_pred = [0, 1, 2, 0, 1, 2]
    assert cost_weighted_score(y_true, y_pred) == 0.0


def test_cost_weighted_score_penalizes_missed_high_worse_than_missed_moderate():
    # true=HIGH(2) predicted=LOW(0): worst-case cost (4.0)
    worst_case = cost_weighted_score([2], [0])
    # true=HIGH(2) predicted=MODERATE(1): lesser cost (2.0)
    lesser_case = cost_weighted_score([2], [1])
    assert worst_case > lesser_case


def test_evaluate_output_includes_cost_score_and_ci_and_n_gate():
    raw_df = generate_synthetic_dataset(n_subjects=20, seed=7)
    clean_df = clean_dataset(raw_df)
    feature_df = build_feature_table(clean_df)
    train_df, test_df = subject_independent_split(feature_df, test_fraction=0.3, seed=7)
    booster = train_model(train_df, num_boost_round=5)

    with tempfile.TemporaryDirectory() as tmp:
        model_path = os.path.join(tmp, "model.json")
        booster.save_model(model_path)
        results = evaluate(model_path, test_df)

    assert "cost_weighted_score" in results
    assert results["cost_weighted_score"] >= 0
    assert "per_class_bootstrap_ci" in results
    for label_stats in results["per_class_bootstrap_ci"].values():
        assert "sensitivity_ci" in label_stats
        assert "specificity_ci" in label_stats
    assert "minimum_n_gate" in results
    # 20 synthetic subjects is well under MIN_SUBJECTS_N -- gate must correctly fail
    assert results["minimum_n_gate"]["passed"] is False
    # accuracy exists inside sklearn's classification_report (unavoidable --
    # that's the library's own dict shape) but must never be surfaced as a
    # top-level reported metric or printed by main() -- see the explicit
    # caveat this key documents.
    assert "accuracy_deliberately_not_reported" in results
