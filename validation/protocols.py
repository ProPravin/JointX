"""
Honest evaluation protocols for small-N clinical data (spec: honest
evaluation for small N; generalization checks).

training/split.py's single random subject-independent holdout stays as the
FINAL reported evaluation, but a single split of a small dataset is a noisy
estimate of anything. This module adds:
  - repeated_group_kfold(): resampled subject-level CV so a metric's spread
    across folds is visible, not just one lucky/unlucky split
  - bootstrap_ci(): a confidence interval on any metric -- never report a
    point estimate without one
  - minimum_n_gate(): refuses to let evaluate.py present numbers as
    meaningful below a subject-count floor
  - temporal_split(): train-on-earlier/test-on-later, because real
    deployment is temporal, not randomly shuffled
  - leave_one_site_out() / leave_one_device_out(): the queries that make
    cross-site and cross-device generalization actually measurable, which
    requires screenings.device_id / patients.facility_name to exist (they
    do -- see database/schema.sql)
"""
import numpy as np
import pandas as pd

from config.model_config import (
    MIN_SUBJECTS_N,
    MIN_MINORITY_CLASS_SUBJECTS_N,
    SITE_OR_DEVICE_SENSITIVITY_DROP_BLOCKER_PP,
)


def minimum_n_gate(df: pd.DataFrame, subject_col: str = "subject_id", label_col: str = "risk_label") -> dict:
    """
    Returns {"passed": bool, "reason": str, "n_subjects": int,
    "minority_class_n": int}. evaluate.py must prefix its output
    "STATISTICALLY UNRELIABLE -- N TOO SMALL" (and
    backend/services/model_status_service.py must refuse to serve numbers)
    whenever passed is False.
    """
    n_subjects = df[subject_col].nunique()
    class_subject_counts = df.groupby(label_col)[subject_col].nunique()
    minority_class_n = int(class_subject_counts.min()) if len(class_subject_counts) else 0

    reasons = []
    if n_subjects < MIN_SUBJECTS_N:
        reasons.append(f"only {n_subjects} subjects (minimum {MIN_SUBJECTS_N})")
    if minority_class_n < MIN_MINORITY_CLASS_SUBJECTS_N:
        reasons.append(f"minority class has only {minority_class_n} subjects (minimum {MIN_MINORITY_CLASS_SUBJECTS_N})")

    return {
        "passed": not reasons,
        "reason": "; ".join(reasons) if reasons else "sample size adequate",
        "n_subjects": n_subjects,
        "minority_class_n": minority_class_n,
    }


def repeated_group_kfold(df: pd.DataFrame, n_splits: int = 5, n_repeats: int = 5,
                          group_col: str = "subject_id", seed: int = 42):
    """
    Yields (train_df, test_df) pairs, n_splits * n_repeats times total, each
    respecting subject-level grouping (no subject appears in both train and
    test within a fold) -- a manual implementation since scikit-learn does
    not ship a RepeatedGroupKFold. Each repeat reshuffles the group order
    with a different seed so repeats aren't identical to each other.
    """
    groups = df[group_col].unique()
    rng = np.random.default_rng(seed)

    for repeat in range(n_repeats):
        shuffled_groups = groups.copy()
        rng.shuffle(shuffled_groups)
        folds = np.array_split(shuffled_groups, n_splits)

        for fold_idx in range(n_splits):
            test_groups = set(folds[fold_idx])
            test_mask = df[group_col].isin(test_groups)
            yield df[~test_mask].copy(), df[test_mask].copy()


def bootstrap_ci(values, n_bootstrap: int = 1000, ci: float = 0.95, seed: int = 42) -> dict:
    """
    Generic percentile bootstrap CI over an array of per-fold (or
    per-subject) metric values. Returns {"point_estimate", "ci_low",
    "ci_high", "n_bootstrap"}. NEVER print a point estimate elsewhere
    without pairing it with this interval (spec requirement).
    """
    values = np.asarray(values, dtype=float)
    values = values[~np.isnan(values)]
    if len(values) == 0:
        return {"point_estimate": None, "ci_low": None, "ci_high": None, "n_bootstrap": 0}

    rng = np.random.default_rng(seed)
    boot_means = [rng.choice(values, size=len(values), replace=True).mean() for _ in range(n_bootstrap)]
    alpha = (1 - ci) / 2
    return {
        "point_estimate": float(values.mean()),
        "ci_low": float(np.quantile(boot_means, alpha)),
        "ci_high": float(np.quantile(boot_means, 1 - alpha)),
        "n_bootstrap": n_bootstrap,
    }


def temporal_split(df: pd.DataFrame, date_col: str = "started_at", test_fraction: float = 0.2):
    """
    Train on earlier screenings, test on the most recent ones -- deployment
    is temporal (the model is used on future patients), not a random
    shuffle, so this is reported ALONGSIDE the random subject-independent
    split, not instead of it. Requires date_col in df (join it in from
    screenings.started_at before calling, since export_dataset.py's default
    CSV doesn't include it by default).
    """
    sorted_df = df.sort_values(date_col)
    n_test = max(1, int(len(sorted_df) * test_fraction))
    return sorted_df.iloc[:-n_test].copy(), sorted_df.iloc[-n_test:].copy()


def leave_one_site_out(df: pd.DataFrame, site_col: str = "facility_name"):
    """
    Yields (train_df, test_df, held_out_site) for each distinct site --
    train on every other site, test on the one held out. A sensitivity drop
    of more than SITE_OR_DEVICE_SENSITIVITY_DROP_BLOCKER_PP percentage
    points on any held-out site versus the overall pooled sensitivity is a
    DEPLOYMENT BLOCKER (caller computes the actual sensitivities; see
    deployment_blocker_check() below).
    """
    for site in df[site_col].dropna().unique():
        test_mask = df[site_col] == site
        yield df[~test_mask].copy(), df[test_mask].copy(), site


def leave_one_device_out(df: pd.DataFrame, device_col: str = "device_id"):
    """Same idea as leave_one_site_out(), grouped by capture device instead of facility."""
    for device in df[device_col].dropna().unique():
        test_mask = df[device_col] == device
        yield df[~test_mask].copy(), df[test_mask].copy(), device


def deployment_blocker_check(overall_sensitivity: float, subgroup_sensitivity: float,
                              threshold_pp: float = SITE_OR_DEVICE_SENSITIVITY_DROP_BLOCKER_PP) -> dict:
    """
    Returns {"blocked": bool, "drop_pp": float}. Percentage-point drop, not
    relative -- a drop from 90% to 78% is a 12pp drop, which matters more
    than a relative-percentage framing would suggest at these small sample
    sizes.
    """
    drop_pp = (overall_sensitivity - subgroup_sensitivity) * 100
    return {"blocked": drop_pp > threshold_pp, "drop_pp": round(drop_pp, 1)}
