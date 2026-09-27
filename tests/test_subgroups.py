"""Spec: subgroup report covers every stratum; flags a real fairness gap."""
import pandas as pd

from validation.subgroups import subgroup_report, age_band, bmi_band, overall_sensitivity


def test_age_band_buckets():
    assert age_band(35) == "under_40"
    assert age_band(45) == "40-49"
    assert age_band(55) == "50-59"
    assert age_band(65) == "60-69"
    assert age_band(75) == "70+"
    assert age_band(None) == "unknown"


def test_bmi_band_buckets():
    assert bmi_band(17) == "underweight"
    assert bmi_band(22) == "normal"
    assert bmi_band(27) == "overweight"
    assert bmi_band(35) == "obese"


def test_overall_sensitivity_perfect_predictions():
    y_true = ["LOW", "MODERATE", "HIGH", "LOW", "MODERATE", "HIGH"]
    y_pred = y_true[:]
    assert overall_sensitivity(pd.Series(y_true), pd.Series(y_pred)) == 1.0


def _build_fairness_gap_dataset():
    """
    Two age groups, both n=20. Group A: model gets HIGH right every time.
    Group B: model systematically misses HIGH (predicts LOW instead) --
    a real, deliberate sensitivity gap the audit should catch.
    """
    rows = []
    for i in range(20):
        rows.append({"age": 45, "risk_label": "HIGH", "predicted_label": "HIGH"})
    for i in range(20):
        rows.append({"age": 75, "risk_label": "HIGH", "predicted_label": "LOW"})
    return pd.DataFrame(rows)


def test_subgroup_report_flags_real_sensitivity_gap():
    df = _build_fairness_gap_dataset()
    report = subgroup_report(df)  # age_band gets computed internally from "age"
    assert "age_band" in report["subgroups"]
    bands = report["subgroups"]["age_band"]
    assert "40-49" in bands and "70+" in bands
    assert bands["40-49"]["sensitivity"] == 1.0
    assert bands["70+"]["sensitivity"] == 0.0
    assert len(report["deployment_blockers"]) >= 1
    assert any(b["group_value"] == "70+" for b in report["deployment_blockers"])


def test_subgroup_report_marks_small_groups_as_insufficient_n():
    df = pd.DataFrame([
        {"age": 45, "risk_label": "LOW", "predicted_label": "LOW"},
        {"age": 45, "risk_label": "LOW", "predicted_label": "LOW"},
    ])
    report = subgroup_report(df)
    entry = report["subgroups"]["age_band"]["40-49"]
    assert entry["insufficient_n"] is True


def test_subgroup_report_covers_every_available_stratum():
    df = pd.DataFrame([
        {"age": 45, "bmi": 22, "sex": "F", "habitual_squatting": 1,
         "risk_label": "LOW", "predicted_label": "LOW"} for _ in range(10)
    ] + [
        {"age": 65, "bmi": 30, "sex": "M", "habitual_squatting": 0,
         "risk_label": "HIGH", "predicted_label": "HIGH"} for _ in range(10)
    ])
    report = subgroup_report(df)
    for expected_group_col in ("age_band", "sex", "bmi_band", "habitual_squatting"):
        assert expected_group_col in report["subgroups"], f"missing stratum: {expected_group_col}"
