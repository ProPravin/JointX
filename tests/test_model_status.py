"""Spec: P2 #8 -- model status honesty."""
import os

from backend.services import model_status_service
from config.settings import Config


def test_no_evaluation_reported_when_no_model_file_exists():
    original = Config.MODEL_PATH
    try:
        Config.MODEL_PATH = "/nonexistent/path/model.json"
        result = model_status_service.get_model_performance()
        assert result["evaluation_available"] is False
        assert result["is_prototype"] is True
        assert "no trained model" in result["reason"].lower()
    finally:
        Config.MODEL_PATH = original


def test_synthetic_results_are_never_served_as_real(tmp_path):
    fake_model = tmp_path / "model.json"
    fake_model.write_text("{}")
    fake_results = tmp_path.parent / "training" / "datasets" / "evaluation_results.json"

    original_model_path = Config.MODEL_PATH
    original_results_path = model_status_service.EVALUATION_RESULTS_PATH
    try:
        Config.MODEL_PATH = str(fake_model)
        os.makedirs(fake_results.parent, exist_ok=True)
        fake_results.write_text('{"synthetic": true, "stamp": "SYNTHETIC"}')
        model_status_service.EVALUATION_RESULTS_PATH = str(fake_results)

        result = model_status_service.get_model_performance()
        assert result["evaluation_available"] is False
        assert "synthetic" in result["reason"].lower()
    finally:
        Config.MODEL_PATH = original_model_path
        model_status_service.EVALUATION_RESULTS_PATH = original_results_path


def test_model_performance_endpoint_is_honest(app, logged_in_client):
    res = logged_in_client.get("/api/model/performance")
    assert res.status_code == 200
    data = res.get_json()["data"]
    # In this repository, no model file exists, so this must always be honest about that.
    assert data["evaluation_available"] is False


def test_pipeline_smoke_test_runs_end_to_end_on_tiny_synthetic_data():
    """Fast variant of training/pipeline_smoke_test.py's own __main__ run, using a small N for test speed."""
    from training.pipeline_smoke_test import generate_synthetic_dataset, STAMP
    from training.preprocessing import clean_dataset
    from training.feature_engineering import build_feature_table
    from training.split import subject_independent_split
    from training.train import train_model
    from training.evaluate import evaluate
    import tempfile

    assert "SYNTHETIC" in STAMP
    assert "NOT A PERFORMANCE CLAIM" in STAMP

    raw_df = generate_synthetic_dataset(n_subjects=20, seed=1)
    clean_df = clean_dataset(raw_df)
    feature_df = build_feature_table(clean_df)
    train_df, test_df = subject_independent_split(feature_df, test_fraction=0.3, seed=1)
    assert len(train_df) > 0 and len(test_df) > 0

    booster = train_model(train_df, num_boost_round=5)
    with tempfile.TemporaryDirectory() as tmp:
        model_path = os.path.join(tmp, "SYNTHETIC_test_model.json")
        booster.save_model(model_path)
        results = evaluate(model_path, test_df)
    assert "confusion_matrix" in results
    assert results["n_test_samples"] == len(test_df)
