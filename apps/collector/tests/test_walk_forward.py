"""Tests for ml.walk_forward -- split correctness and leakage detection."""
import pytest
from src.hundredx.ml.walk_forward import (
    get_split,
    split_rows,
    walk_forward_folds,
    assert_no_test_leakage,
    SPLITS,
    WalkForwardFold,
)


# ── get_split ────────────────────────────────────────────────────────────────

def test_get_split_returns_valid_splits():
    for name in ("train", "embargo_1", "val", "embargo_2", "test"):
        s = get_split(name)
        assert s.split_name == name
        assert s.start <= s.end


def test_get_split_unknown_raises():
    with pytest.raises(ValueError, match="Unknown split"):
        get_split("nonexistent_split")


def test_train_ends_before_embargo_1():
    train = get_split("train")
    embargo = get_split("embargo_1")
    assert train.end < embargo.start


def test_val_ends_before_embargo_2():
    val = get_split("val")
    embargo = get_split("embargo_2")
    assert val.end < embargo.start


def test_embargo_2_ends_before_test():
    embargo = get_split("embargo_2")
    test = get_split("test")
    assert embargo.end < test.start


# ── SplitResult.contains ────────────────────────────────────────────────────

def test_contains_in_range():
    s = get_split("train")
    assert s.contains("2010-06-15")


def test_contains_at_boundary():
    s = get_split("train")
    assert s.contains("2000-01-01")
    assert s.contains("2018-12-31")


def test_contains_outside_range():
    s = get_split("train")
    assert not s.contains("2019-01-01")  # in embargo_1


# ── SplitResult.filter ───────────────────────────────────────────────────────

def test_filter_returns_in_range():
    s = get_split("train")
    rows = [
        {"snapshot_date": "2010-01-01"},
        {"snapshot_date": "2019-06-01"},  # embargo_1
        {"snapshot_date": "2015-05-20"},
    ]
    filtered = s.filter(rows)
    assert len(filtered) == 2
    assert all(r["snapshot_date"] <= "2018-12-31" for r in filtered)


# ── split_rows ───────────────────────────────────────────────────────────────

def test_split_rows_categorizes_all():
    rows = [
        {"snapshot_date": "2010-01-01"},   # train
        {"snapshot_date": "2019-03-01"},   # embargo_1
        {"snapshot_date": "2020-06-01"},   # val
        {"snapshot_date": "2023-04-01"},   # embargo_2
        {"snapshot_date": "2024-01-01"},   # test
    ]
    result = split_rows(rows)
    assert len(result["train"]) == 1
    assert len(result["embargo_1"]) == 1
    assert len(result["val"]) == 1
    assert len(result["embargo_2"]) == 1
    assert len(result["test"]) == 1


def test_split_rows_no_overlap():
    """Each row should belong to exactly one split."""
    dates = [
        "2010-01-01", "2018-12-31",   # train
        "2019-01-01", "2019-06-30",   # embargo_1
        "2019-07-01", "2022-12-31",   # val
        "2023-01-01", "2023-06-30",   # embargo_2
        "2023-07-01", "2025-01-01",   # test
    ]
    rows = [{"snapshot_date": d} for d in dates]
    result = split_rows(rows)
    total = sum(len(v) for v in result.values())
    assert total == len(dates)


def test_split_rows_empty_list():
    result = split_rows([])
    assert all(len(v) == 0 for v in result.values())


# ── walk_forward_folds ───────────────────────────────────────────────────────

def _make_rows(dates):
    return [{"snapshot_date": d, "label_10x_24m": 0} for d in dates]


def test_walk_forward_folds_returns_list():
    rows = _make_rows(
        [f"201{y}-06-01" for y in range(0, 9)] +
        [f"201{y}-09-01" for y in range(3, 9)]
    )
    folds = walk_forward_folds(rows)
    assert isinstance(folds, list)
    assert all(isinstance(f, WalkForwardFold) for f in folds)


def test_walk_forward_folds_no_leakage():
    """Val rows must not overlap with train rows for any fold."""
    rows = _make_rows([f"201{y}-01-01" for y in range(8)])
    folds = walk_forward_folds(rows)
    for fold in folds:
        train = fold.train_rows(rows)
        val = fold.val_rows(rows)
        train_dates = {r["snapshot_date"] for r in train}
        val_dates = {r["snapshot_date"] for r in val}
        assert train_dates.isdisjoint(val_dates), \
            f"Fold {fold.fold_idx}: train/val overlap detected"


def test_walk_forward_folds_train_before_val():
    """All train dates must precede val dates."""
    rows = _make_rows([f"201{y}-01-01" for y in range(8)])
    folds = walk_forward_folds(rows)
    for fold in folds:
        train = fold.train_rows(rows)
        val = fold.val_rows(rows)
        if train and val:
            max_train = max(r["snapshot_date"] for r in train)
            min_val = min(r["snapshot_date"] for r in val)
            assert max_train < min_val, \
                f"Fold {fold.fold_idx}: train date {max_train} >= val date {min_val}"


def test_walk_forward_empty_rows():
    folds = walk_forward_folds([])
    assert folds == []


# ── assert_no_test_leakage ───────────────────────────────────────────────────

def test_assert_no_leakage_passes_for_clean_data():
    rows = [{"snapshot_date": "2015-01-01"}, {"snapshot_date": "2018-12-31"}]
    assert_no_test_leakage(rows)  # should not raise


def test_assert_no_leakage_raises_for_test_data():
    rows = [
        {"snapshot_date": "2010-01-01"},
        {"snapshot_date": "2024-06-01"},  # test period
    ]
    with pytest.raises(ValueError, match="DATA LEAKAGE"):
        assert_no_test_leakage(rows)


def test_assert_no_leakage_raises_for_embargo_2():
    rows = [{"snapshot_date": "2023-03-01"}]  # in embargo_2
    with pytest.raises(ValueError, match="DATA LEAKAGE"):
        assert_no_test_leakage(rows)


def test_assert_no_leakage_empty_passes():
    assert_no_test_leakage([])


def test_assert_no_leakage_custom_date_key():
    rows = [{"date": "2010-01-01"}]
    assert_no_test_leakage(rows, date_key="date")


def test_assert_no_leakage_custom_key_leaks():
    rows = [{"date": "2024-01-01"}]
    with pytest.raises(ValueError, match="DATA LEAKAGE"):
        assert_no_test_leakage(rows, date_key="date")


# ── splits are complete and non-overlapping ──────────────────────────────────

def test_splits_complete_coverage():
    """Every sampled date from 2000-2025 should fall into exactly one split."""
    from datetime import date, timedelta

    current = date(2000, 1, 1)
    end = date(2025, 12, 31)
    unmatched = []
    while current <= end:
        d = current.isoformat()
        matched = sum(
            1 for name, (s, e) in SPLITS.items()
            if s <= d <= e
        )
        if matched == 0:
            unmatched.append(d)
        current += timedelta(days=180)  # sample every 6 months for speed

    assert len(unmatched) == 0, f"Dates not in any split: {unmatched[:5]}"


def test_splits_no_date_overlap():
    """No single date should belong to two splits (checked daily at boundaries)."""
    from datetime import date, timedelta

    # Check boundary zone only
    start = date(2018, 12, 28)
    end = date(2023, 7, 5)
    current = start
    while current <= end:
        d = current.isoformat()
        matched = [
            name for name, (s, e) in SPLITS.items()
            if s <= d <= e
        ]
        assert len(matched) <= 1, \
            f"Date {d} in multiple splits: {matched}"
        current += timedelta(days=1)
