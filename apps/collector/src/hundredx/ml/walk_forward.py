"""Walk-forward purged cross-validation split.

López de Prado (2018) Ch.7 방식:
  - Train / Embargo / Validation / Embargo / Test
  - Embargo 기간은 label leakage 방지 (24개월 라벨 horizon 때문에 6개월 embargo)
  - Test 기간은 절대 재튜닝 금지 — 최종 성과 평가에만 사용

Splits (fixed):
  Train:      2000-01-01 ~ 2018-12-31
  Embargo 1:  2019-01-01 ~ 2019-06-30
  Val:        2019-07-01 ~ 2022-12-31
  Embargo 2:  2023-01-01 ~ 2023-06-30
  Test:       2023-07-01 ~ today        ← 절대 손대지 말 것
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

SPLITS: dict[str, tuple[str, str]] = {
    "train":      ("2000-01-01", "2018-12-31"),
    "embargo_1":  ("2019-01-01", "2019-06-30"),
    "val":        ("2019-07-01", "2022-12-31"),
    "embargo_2":  ("2023-01-01", "2023-06-30"),
    "test":       ("2023-07-01", "2099-12-31"),
}

# Walk-forward windows for time-series CV within train period
# 각 fold: train_end 이후 6개월 embargo + 12개월 val
_WALK_FORWARD_FOLDS = [
    # (fold_train_end, fold_val_start, fold_val_end)
    ("2012-12-31", "2013-07-01", "2014-06-30"),
    ("2013-12-31", "2014-07-01", "2015-06-30"),
    ("2014-12-31", "2015-07-01", "2016-06-30"),
    ("2015-12-31", "2016-07-01", "2017-06-30"),
    ("2016-12-31", "2017-07-01", "2018-06-30"),
]


@dataclass
class SplitResult:
    split_name: str
    start: str
    end: str

    def contains(self, date_str: str) -> bool:
        return self.start <= date_str <= self.end

    def filter(self, rows: list[dict], date_key: str = "snapshot_date") -> list[dict]:
        return [r for r in rows if self.start <= (r.get(date_key) or "") <= self.end]


def get_split(name: str) -> SplitResult:
    """특정 split의 날짜 범위 반환."""
    if name not in SPLITS:
        raise ValueError(f"Unknown split: {name}. Valid: {list(SPLITS)}")
    start, end = SPLITS[name]
    return SplitResult(split_name=name, start=start, end=end)


def split_rows(
    rows: list[dict],
    date_key: str = "snapshot_date",
) -> dict[str, list[dict]]:
    """샘플 목록을 split별로 분류."""
    result: dict[str, list[dict]] = {k: [] for k in SPLITS}
    for r in rows:
        d = r.get(date_key) or ""
        for split_name, (start, end) in SPLITS.items():
            if start <= d <= end:
                result[split_name].append(r)
                break
    return result


@dataclass
class WalkForwardFold:
    fold_idx: int
    train_start: str
    train_end: str
    val_start: str
    val_end: str

    def train_rows(self, rows: list[dict], date_key: str = "snapshot_date") -> list[dict]:
        return [r for r in rows if self.train_start <= (r.get(date_key) or "") <= self.train_end]

    def val_rows(self, rows: list[dict], date_key: str = "snapshot_date") -> list[dict]:
        return [r for r in rows if self.val_start <= (r.get(date_key) or "") <= self.val_end]


def walk_forward_folds(train_rows: list[dict], date_key: str = "snapshot_date") -> list[WalkForwardFold]:
    """Train 기간 내 walk-forward fold 목록 생성."""
    folds = []
    for i, (train_end, val_start, val_end) in enumerate(_WALK_FORWARD_FOLDS):
        fold = WalkForwardFold(
            fold_idx=i,
            train_start="2000-01-01",
            train_end=train_end,
            val_start=val_start,
            val_end=val_end,
        )
        tr = fold.train_rows(train_rows, date_key)
        vl = fold.val_rows(train_rows, date_key)
        if tr and vl:
            folds.append(fold)
    return folds


def assert_no_test_leakage(df_or_rows: Any, date_key: str = "snapshot_date") -> None:
    """Test 기간 데이터가 포함됐는지 검사 — 모델 학습/튜닝 전에 반드시 호출."""
    test_start, _ = SPLITS["test"]
    embargo_start, _ = SPLITS["embargo_2"]

    rows_to_check = df_or_rows
    try:
        # DataFrame
        rows_to_check = df_or_rows.to_dict("records")
    except AttributeError:
        pass

    for r in rows_to_check:
        d = r.get(date_key) or ""
        if d >= embargo_start:
            raise ValueError(
                f"DATA LEAKAGE DETECTED: row with date {d!r} is in embargo/test period "
                f"(>= {embargo_start}). Remove test data before training."
            )
