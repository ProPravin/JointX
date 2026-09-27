"""Spec: metrics refused below the minimum-N threshold."""
import pandas as pd

from validation.protocols import minimum_n_gate
from backend.services import model_status_service
from config.model_config import MIN_SUBJECTS_N, MIN_MINORITY_CLASS_SUBJECTS_N


def _make_df(n_low_subjects, n_moderate_subjects, n_high_subjects):
    rows = []
    subject_id = 0
    for _ in range(n_low_subjects):
        subject_id += 1
        rows.append({"subject_id": subject_id, "risk_label": "LOW"})
    for _ in range(n_moderate_subjects):
        subject_id += 1
        rows.append({"subject_id": subject_id, "risk_label": "MODERATE"})
    for _ in range(n_high_subjects):
        subject_id += 1
        rows.append({"subject_id": subject_id, "risk_label": "HIGH"})
    return pd.DataFrame(rows)


def test_gate_fails_with_too_few_total_subjects():
    df = _make_df(5, 5, 5)  # 15 total, well under MIN_SUBJECTS_N
    result = minimum_n_gate(df)
    assert result["passed"] is False
    assert "subjects" in result["reason"]
    assert result["n_subjects"] == 15


def test_gate_fails_with_too_few_minority_class_subjects():
    n_per_majority = MIN_SUBJECTS_N  # plenty of total subjects
    df = _make_df(n_per_majority, n_per_majority, 2)  # HIGH class starved
    result = minimum_n_gate(df)
    assert result["passed"] is False
    assert "minority class" in result["reason"]


def test_gate_passes_with_adequate_sample_size():
    per_class = max(MIN_SUBJECTS_N // 3 + 1, MIN_MINORITY_CLASS_SUBJECTS_N + 1)
    df = _make_df(per_class, per_class, per_class)
    result = minimum_n_gate(df)
    assert result["passed"] is True
    assert result["minority_class_n"] >= MIN_MINORITY_CLASS_SUBJECTS_N


def test_model_status_service_refuses_small_n_evaluation(tmp_path, monkeypatch):
    fake_model = tmp_path / "model.json"
    fake_model.write_text("{}")
    fake_results = tmp_path / "evaluation_results.json"
    fake_results.write_text(
        '{"minimum_n_gate": {"passed": false, "reason": "only 15 subjects (minimum 40)"}, '
        '"confusion_matrix": [[1,0,0],[0,1,0],[0,0,1]]}'
    )

    from config.settings import Config

    monkeypatch.setattr(Config, "MODEL_PATH", str(fake_model))
    monkeypatch.setattr(model_status_service, "EVALUATION_RESULTS_PATH", str(fake_results))

    result = model_status_service.get_model_performance()
    assert result["evaluation_available"] is False
    assert "STATISTICALLY UNRELIABLE" in result["reason"]
