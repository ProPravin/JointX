"""GroupKFold repeated CV, bootstrap CIs, temporal split, leave-one-site/device-out."""
import pandas as pd

from validation.protocols import (
    repeated_group_kfold,
    bootstrap_ci,
    temporal_split,
    leave_one_site_out,
    leave_one_device_out,
    deployment_blocker_check,
)


def _make_subject_df(n_subjects=20, rows_per_subject=2):
    rows = []
    for subj in range(n_subjects):
        for _ in range(rows_per_subject):
            rows.append({"subject_id": subj, "value": subj})
    return pd.DataFrame(rows)


def test_repeated_group_kfold_never_splits_a_subject_across_folds():
    df = _make_subject_df(n_subjects=20)
    fold_count = 0
    for train_df, test_df in repeated_group_kfold(df, n_splits=5, n_repeats=3):
        fold_count += 1
        train_subjects = set(train_df["subject_id"])
        test_subjects = set(test_df["subject_id"])
        assert not (train_subjects & test_subjects), "a subject leaked across train/test in one fold"
        assert len(test_subjects) > 0
    assert fold_count == 5 * 3


def test_repeated_group_kfold_repeats_actually_differ():
    df = _make_subject_df(n_subjects=20)
    first_repeat_test_sets = []
    for i, (_, test_df) in enumerate(repeated_group_kfold(df, n_splits=5, n_repeats=2)):
        if i < 5:
            first_repeat_test_sets.append(frozenset(test_df["subject_id"]))
    second_repeat_test_sets = []
    for i, (_, test_df) in enumerate(repeated_group_kfold(df, n_splits=5, n_repeats=2)):
        if i >= 5:
            second_repeat_test_sets.append(frozenset(test_df["subject_id"]))
    assert set(first_repeat_test_sets) != set(second_repeat_test_sets)


def test_bootstrap_ci_contains_point_estimate():
    values = [0.7, 0.75, 0.8, 0.72, 0.78, 0.74, 0.76]
    result = bootstrap_ci(values)
    assert result["ci_low"] <= result["point_estimate"] <= result["ci_high"]
    assert result["n_bootstrap"] == 1000


def test_bootstrap_ci_handles_empty_input():
    result = bootstrap_ci([])
    assert result["point_estimate"] is None


def test_temporal_split_orders_by_date_not_randomly():
    df = pd.DataFrame({
        "started_at": ["2026-01-01", "2026-02-01", "2026-03-01", "2026-04-01", "2026-05-01"],
        "value": [1, 2, 3, 4, 5],
    })
    train_df, test_df = temporal_split(df, test_fraction=0.4)
    assert test_df["started_at"].min() > train_df["started_at"].max()
    assert len(test_df) == 2


def test_leave_one_site_out_excludes_held_out_site_from_train():
    df = pd.DataFrame({
        "facility_name": ["A", "A", "B", "B", "C", "C"],
        "value": [1, 2, 3, 4, 5, 6],
    })
    sites_seen = set()
    for train_df, test_df, site in leave_one_site_out(df):
        sites_seen.add(site)
        assert site not in set(train_df["facility_name"])
        assert set(test_df["facility_name"]) == {site}
    assert sites_seen == {"A", "B", "C"}


def test_leave_one_device_out_excludes_held_out_device_from_train():
    df = pd.DataFrame({
        "device_id": ["dev1", "dev1", "dev2", "dev2"],
        "value": [1, 2, 3, 4],
    })
    for train_df, test_df, device in leave_one_device_out(df):
        assert device not in set(train_df["device_id"])


def test_deployment_blocker_check_flags_large_drop():
    result = deployment_blocker_check(overall_sensitivity=0.90, subgroup_sensitivity=0.70)
    assert result["blocked"] is True
    assert result["drop_pp"] == 20.0


def test_deployment_blocker_check_allows_small_drop():
    result = deployment_blocker_check(overall_sensitivity=0.90, subgroup_sensitivity=0.85)
    assert result["blocked"] is False
