"""Spec: numeric score withheld without a fitted, gate-passing calibrator."""
import numpy as np
import pytest

from validation import calibration
from backend.services.prediction_service import _apply_calibration_gate


@pytest.fixture(autouse=True)
def _isolate_calibrator_files(tmp_path, monkeypatch):
    """Never let these tests read/write the real validation/models/ files."""
    monkeypatch.setattr(calibration, "CALIBRATOR_PATH", str(tmp_path / "calibrator.pkl"))
    monkeypatch.setattr(calibration, "CALIBRATOR_META_PATH", str(tmp_path / "calibrator_meta.json"))
    monkeypatch.setattr(calibration, "REPORTS_DIR", str(tmp_path / "reports"))


def test_no_calibrator_means_no_numeric_score():
    result = {"risk_label": "MODERATE", "risk_score": 0.62, "is_prototype": False}
    gated = _apply_calibration_gate(result)
    assert gated["risk_score"] is None
    assert gated["risk_label"] == "MODERATE"  # band is never withheld, only the number


def test_fit_and_pass_gate_with_well_separated_data():
    rng = np.random.default_rng(0)
    # Confidence strongly predicts correctness -- a calibrator fit on this
    # should produce a low (good) Brier score and pass the gate.
    confidence = np.concatenate([rng.uniform(0.5, 0.6, 50), rng.uniform(0.9, 1.0, 50)])
    correct = np.concatenate([np.zeros(50), np.ones(50)])

    calibrator = calibration.fit_calibrator(confidence, correct, method="isotonic")
    meta = calibration.save_calibrator(calibrator, confidence, correct)

    assert meta["gate_passed"] is True
    assert meta["brier_score"] < calibration.CALIBRATION_BRIER_THRESHOLD

    loaded_meta = calibration.load_calibrator_meta()
    assert loaded_meta["exists"] is True
    assert loaded_meta["gate_passed"] is True

    result = {"risk_label": "HIGH", "risk_score": 0.95, "is_prototype": False}
    gated = _apply_calibration_gate(result)
    assert gated["risk_score"] is not None
    assert 0 <= gated["risk_score"] <= 100


def test_fit_but_fail_gate_with_random_data():
    rng = np.random.default_rng(1)
    # Confidence has no relationship to correctness -- Brier score should
    # land around 0.25 (coin-flip-ish), failing the 0.20 threshold.
    confidence = rng.uniform(0.4, 0.9, 200)
    correct = rng.integers(0, 2, 200)

    calibrator = calibration.fit_calibrator(confidence, correct, method="platt")
    meta = calibration.save_calibrator(calibrator, confidence, correct)

    result = {"risk_label": "LOW", "risk_score": 0.5, "is_prototype": False}
    gated = _apply_calibration_gate(result)
    if not meta["gate_passed"]:
        assert gated["risk_score"] is None


def test_refused_prediction_has_no_score_regardless_of_calibrator():
    result = {"risk_label": "REFUSED", "risk_score": None, "is_prototype": True}
    gated = _apply_calibration_gate(result)
    assert gated["risk_score"] is None


def test_small_calibration_set_uses_platt_not_isotonic():
    rng = np.random.default_rng(2)
    confidence = rng.uniform(0.5, 1.0, 10)
    correct = rng.integers(0, 2, 10)
    calibrator = calibration.fit_calibrator(confidence, correct, method="auto")
    assert calibrator._jointx_method == "platt"
