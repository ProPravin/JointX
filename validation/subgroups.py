"""
Subgroup / fairness audit (spec: NER-specific subgroup audit).

Reports sensitivity, specificity, and refusal rate broken down by age band,
sex, site, BMI band, and habitual-squatting status, and flags any subgroup
whose sensitivity is meaningfully below the overall figure. This is where
the habitual_squatting feature (fusion/feature_schema.py) actually gets
used for something -- checking whether the model performs worse for
patients whose baseline joint ROM is elevated by routine squatting, rather
than just adding the feature and hoping.

NOTE: occupation class (agricultural / non-agricultural) is named in the
original spec as a subgroup dimension but has no dedicated structured field
in this schema yet (only questionnaire.lifestyle_notes free text) -- this
is a documented gap, not silently skipped: occupation-based subgroup
reporting is unavailable until that field exists.
"""
import numpy as np
import pandas as pd

from config.model_config import RISK_LABELS, SUBGROUP_SENSITIVITY_DROP_BLOCKER_PP


def age_band(age) -> str:
    if age is None or (isinstance(age, float) and np.isnan(age)):
        return "unknown"
    age = int(age)
    if age < 40:
        return "under_40"
    if age < 50:
        return "40-49"
    if age < 60:
        return "50-59"
    if age < 70:
        return "60-69"
    return "70+"


def bmi_band(bmi) -> str:
    if bmi is None or (isinstance(bmi, float) and np.isnan(bmi)):
        return "unknown"
    if bmi < 18.5:
        return "underweight"
    if bmi < 25:
        return "normal"
    if bmi < 30:
        return "overweight"
    return "obese"


def sensitivity_for_class(y_true, y_pred, cls) -> float:
    """Recall for one class: TP / (TP + FN). NaN if the class never appears in y_true (undefined, not zero)."""
    true_positive_mask = y_true == cls
    n_true = true_positive_mask.sum()
    if n_true == 0:
        return float("nan")
    correct = ((y_true == cls) & (y_pred == cls)).sum()
    return correct / n_true


def specificity_for_class(y_true, y_pred, cls) -> float:
    """TN / (TN + FP) for one-vs-rest. NaN if there are no true negatives to measure against."""
    true_negative_mask = y_true != cls
    n_true_negative = true_negative_mask.sum()
    if n_true_negative == 0:
        return float("nan")
    correct = ((y_true != cls) & (y_pred != cls)).sum()
    return correct / n_true_negative


def overall_sensitivity(y_true, y_pred) -> float:
    """Macro-averaged sensitivity across RISK_LABELS classes present in y_true."""
    y_true, y_pred = np.asarray(y_true), np.asarray(y_pred)
    values = [sensitivity_for_class(y_true, y_pred, cls) for cls in RISK_LABELS]
    values = [v for v in values if not np.isnan(v)]
    return float(np.mean(values)) if values else float("nan")


def subgroup_report(df: pd.DataFrame, y_true_col: str = "risk_label", y_pred_col: str = "predicted_label",
                     group_cols: list = None) -> dict:
    """
    df must have y_true_col and y_pred_col plus whichever of these raw
    columns are available: age, bmi, sex, facility_name, habitual_squatting.
    Age/BMI bands are computed internally, not required pre-binned.

    Returns {"overall": {...}, "subgroups": {group_col: {group_value: {...}}},
    "deployment_blockers": [...]} -- any subgroup with n < 5 is reported as
    "insufficient_n" rather than a computed (and misleadingly precise) number.
    """
    df = df.copy()
    if "age" in df.columns:
        df["age_band"] = df["age"].apply(age_band)
    if "bmi" in df.columns:
        df["bmi_band"] = df["bmi"].apply(bmi_band)

    group_cols = group_cols or [c for c in ("age_band", "sex", "facility_name", "bmi_band", "habitual_squatting") if c in df.columns]

    overall_sens = overall_sensitivity(df[y_true_col], df[y_pred_col])
    result = {"overall": {"sensitivity": overall_sens, "n": len(df)}, "subgroups": {}, "deployment_blockers": []}

    for group_col in group_cols:
        result["subgroups"][group_col] = {}
        for value, subdf in df.groupby(group_col):
            if len(subdf) < 5:
                result["subgroups"][group_col][str(value)] = {"insufficient_n": True, "n": len(subdf)}
                continue

            sens = overall_sensitivity(subdf[y_true_col], subdf[y_pred_col])
            entry = {"sensitivity": sens, "n": len(subdf), "insufficient_n": False}
            result["subgroups"][group_col][str(value)] = entry

            if not np.isnan(sens) and not np.isnan(overall_sens):
                drop_pp = (overall_sens - sens) * 100
                if drop_pp > SUBGROUP_SENSITIVITY_DROP_BLOCKER_PP:
                    result["deployment_blockers"].append({
                        "group_col": group_col, "group_value": str(value),
                        "sensitivity": sens, "drop_pp": round(drop_pp, 1),
                    })

    return result


def refusal_rate_by_subgroup(db_path: str = None) -> dict:
    """
    Refusal rate (predictions.refused=1) by facility, from the LIVE
    database directly -- refused screenings are, by definition, excluded
    from export_dataset.py's labelled CSV (there's no prediction to
    review), so this can't be computed from the same dataframe as
    subgroup_report() above; it needs its own query against the live DB.
    """
    import sqlite3
    from config.settings import Config

    conn = sqlite3.connect(db_path or Config.DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """SELECT p.facility_name, COUNT(*) as total,
                  SUM(CASE WHEN pr.refused = 1 THEN 1 ELSE 0 END) as refused_count
           FROM screenings s
           JOIN patients p ON p.id = s.patient_id
           JOIN predictions pr ON pr.screening_id = s.id
           WHERE s.is_demo = 0
           GROUP BY p.facility_name"""
    ).fetchall()
    conn.close()

    return {
        (row["facility_name"] or "unknown"): {
            "total": row["total"],
            "refused": row["refused_count"],
            "refusal_rate": round(row["refused_count"] / row["total"], 3) if row["total"] else None,
        }
        for row in rows
    }
