"""Confidence calibration 검증기.

Brier score, calibration curve, reliability diagram 계산.
Tetlock-Gardner *Superforecasting* 기준: Brier ≤ 0.25 = superforecaster 수준.
목표: Brier ≤ 0.18.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable


@dataclass
class CalibrationResult:
    n_samples: int
    brier_score: float                  # 0=완벽, 0.25=random
    brier_skill_score: float            # 1 - Brier/Brier_climatology (높을수록 좋음)
    mean_predicted: float
    mean_actual: float
    calibration_bins: list[dict]        # [{bin_center, pred_mean, actual_freq, count}]
    is_calibrated: bool                 # True if max(|pred - actual|) < 0.1 across bins


def compute_brier_score(
    y_pred: list[float],
    y_true: list[int],
) -> float:
    """Brier score = mean squared error of probabilities."""
    if not y_pred:
        return float("nan")
    return sum((p - t) ** 2 for p, t in zip(y_pred, y_true)) / len(y_pred)


def calibration_curve(
    y_pred: list[float],
    y_true: list[int],
    n_bins: int = 10,
) -> list[dict]:
    """예측 확률을 n_bins 구간으로 나눠 실제 빈도와 비교.

    완벽 calibration: pred_mean ≈ actual_freq for every bin.
    Returns: [{"bin_center": 0.05, "pred_mean": 0.06, "actual_freq": 0.07, "count": 42}, ...]
    """
    bins: list[list[tuple[float, int]]] = [[] for _ in range(n_bins)]
    for p, t in zip(y_pred, y_true):
        b = min(int(p * n_bins), n_bins - 1)
        bins[b].append((p, t))

    result = []
    for i, bin_items in enumerate(bins):
        if not bin_items:
            continue
        bin_center = (i + 0.5) / n_bins
        pred_mean = sum(p for p, _ in bin_items) / len(bin_items)
        actual_freq = sum(t for _, t in bin_items) / len(bin_items)
        result.append({
            "bin_center": round(bin_center, 3),
            "pred_mean": round(pred_mean, 4),
            "actual_freq": round(actual_freq, 4),
            "count": len(bin_items),
        })
    return result


def evaluate_calibration(
    y_pred: list[float],
    y_true: list[int],
    n_bins: int = 10,
) -> CalibrationResult:
    """전체 calibration 평가."""
    n = len(y_pred)
    if n == 0:
        return CalibrationResult(
            n_samples=0, brier_score=float("nan"),
            brier_skill_score=float("nan"),
            mean_predicted=0.0, mean_actual=0.0,
            calibration_bins=[], is_calibrated=False,
        )

    brier = compute_brier_score(y_pred, y_true)
    base_rate = sum(y_true) / n
    # Climatology (reference) Brier: always predict base_rate
    brier_clim = base_rate * (1 - base_rate)
    bss = 1.0 - brier / brier_clim if brier_clim > 0 else 0.0

    bins = calibration_curve(y_pred, y_true, n_bins)

    # Max calibration error across bins
    max_error = max(
        abs(b["pred_mean"] - b["actual_freq"])
        for b in bins
        if b["count"] >= 10  # 10개 이상 있는 bin만
    ) if any(b["count"] >= 10 for b in bins) else 1.0

    return CalibrationResult(
        n_samples=n,
        brier_score=round(brier, 4),
        brier_skill_score=round(bss, 4),
        mean_predicted=round(sum(y_pred) / n, 4),
        mean_actual=round(sum(y_true) / n, 4),
        calibration_bins=bins,
        is_calibrated=(max_error < 0.10),
    )


def print_calibration_report(result: CalibrationResult) -> None:
    """텍스트 리포트 출력."""
    grade = (
        "EXCELLENT (≤0.18)" if result.brier_score <= 0.18 else
        "GOOD (≤0.22)" if result.brier_score <= 0.22 else
        "FAIR (≤0.25)" if result.brier_score <= 0.25 else
        "POOR (>0.25)"
    )
    print(f"\n=== Calibration Report (n={result.n_samples}) ===")
    print(f"Brier score:       {result.brier_score:.4f}  [{grade}]")
    print(f"Brier skill score: {result.brier_skill_score:.4f}  (>0 = better than climatology)")
    print(f"Mean predicted:    {result.mean_predicted:.4f}")
    print(f"Mean actual:       {result.mean_actual:.4f}")
    print(f"Calibrated:        {'YES' if result.is_calibrated else 'NO'}")
    print(f"\nCalibration bins:")
    print(f"  {'Bin':>8} {'Pred':>8} {'Actual':>8} {'Count':>8} {'Error':>8}")
    for b in result.calibration_bins:
        err = abs(b["pred_mean"] - b["actual_freq"])
        flag = "  ←" if err > 0.10 else ""
        print(f"  {b['bin_center']:>8.3f} {b['pred_mean']:>8.4f} {b['actual_freq']:>8.4f} "
              f"{b['count']:>8} {err:>8.4f}{flag}")
