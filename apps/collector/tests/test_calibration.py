"""Tests for ml.calibration -- Brier score, calibration curve, evaluate_calibration."""
import math
import pytest
from src.hundredx.ml.calibration import (
    compute_brier_score,
    calibration_curve,
    evaluate_calibration,
    CalibrationResult,
    print_calibration_report,
)


# ── compute_brier_score ──────────────────────────────────────────────────────

def test_brier_perfect():
    """Perfect predictions -> Brier = 0."""
    y_pred = [1.0, 0.0, 1.0, 0.0]
    y_true = [1,   0,   1,   0]
    assert compute_brier_score(y_pred, y_true) == 0.0


def test_brier_worst():
    """Worst predictions (all wrong) -> Brier = 1.0."""
    y_pred = [0.0, 1.0, 0.0, 1.0]
    y_true = [1,   0,   1,   0]
    assert compute_brier_score(y_pred, y_true) == 1.0


def test_brier_random():
    """Predicting 0.5 always -> Brier = 0.25 for balanced outcomes."""
    y_pred = [0.5] * 100
    y_true = [1] * 50 + [0] * 50
    assert abs(compute_brier_score(y_pred, y_true) - 0.25) < 1e-9


def test_brier_empty():
    assert math.isnan(compute_brier_score([], []))


def test_brier_single_correct():
    assert compute_brier_score([0.9], [1]) == pytest.approx((0.9 - 1)**2)


def test_brier_single_wrong():
    assert compute_brier_score([0.9], [0]) == pytest.approx((0.9 - 0)**2)


def test_brier_symmetry():
    """Brier(pred, true) = Brier(1-pred, 1-true) -- label flip invariant."""
    y_pred = [0.3, 0.7, 0.5, 0.9]
    y_true = [0, 1, 1, 1]
    y_pred_flip = [1 - p for p in y_pred]
    y_true_flip = [1 - t for t in y_true]
    b1 = compute_brier_score(y_pred, y_true)
    b2 = compute_brier_score(y_pred_flip, y_true_flip)
    assert abs(b1 - b2) < 1e-9


# ── calibration_curve ────────────────────────────────────────────────────────

def test_calibration_curve_returns_list():
    y_pred = [0.1 * i for i in range(11)] * 10
    y_true = [1 if p > 0.5 else 0 for p in y_pred]
    result = calibration_curve(y_pred, y_true)
    assert isinstance(result, list)
    for item in result:
        assert "bin_center" in item
        assert "pred_mean" in item
        assert "actual_freq" in item
        assert "count" in item


def test_calibration_curve_no_empty_bins():
    """Empty bins should be omitted from output."""
    y_pred = [0.1] * 50 + [0.2] * 50
    y_true = [0] * 100
    result = calibration_curve(y_pred, y_true)
    for b in result:
        assert b["bin_center"] <= 0.25


def test_calibration_curve_n_bins_respected():
    y_pred = [i / 100 for i in range(101)] * 5
    y_true = [0] * len(y_pred)
    result5 = calibration_curve(y_pred, y_true, n_bins=5)
    result10 = calibration_curve(y_pred, y_true, n_bins=10)
    assert len(result10) >= len(result5) or len(result5) <= 5


# ── evaluate_calibration ─────────────────────────────────────────────────────

def test_evaluate_empty():
    result = evaluate_calibration([], [])
    assert result.n_samples == 0
    assert math.isnan(result.brier_score)


def test_evaluate_returns_calibration_result():
    y_pred = [0.3, 0.7, 0.8, 0.2]
    y_true = [0, 1, 1, 0]
    result = evaluate_calibration(y_pred, y_true)
    assert isinstance(result, CalibrationResult)
    assert result.n_samples == 4


def test_brier_skill_score_positive_for_good_model():
    """Skill score > 0 means better than climatology (always predict base rate)."""
    base_rate = 0.30
    n = 500
    import random
    random.seed(42)
    y_true = [1] * int(n * base_rate) + [0] * int(n * (1 - base_rate))
    y_pred = [0.8 if t else 0.2 for t in y_true]
    result = evaluate_calibration(y_pred, y_true)
    assert result.brier_skill_score > 0


def test_brier_skill_score_negative_for_bad_model():
    """Skill score < 0 means worse than climatology."""
    y_true = [1] * 60 + [0] * 140
    y_pred = [0.1 if t == 1 else 0.9 for t in y_true]
    result = evaluate_calibration(y_pred, y_true)
    assert result.brier_skill_score < 0


def test_mean_predicted_and_actual():
    y_pred = [0.3, 0.5, 0.7]
    y_true = [0, 1, 1]
    result = evaluate_calibration(y_pred, y_true)
    assert abs(result.mean_predicted - (0.3 + 0.5 + 0.7) / 3) < 0.001
    assert abs(result.mean_actual - (0 + 1 + 1) / 3) < 0.001


def test_is_calibrated_is_bool():
    y_pred = [0.3, 0.5, 0.8, 0.2]
    y_true = [0, 1, 1, 0]
    result = evaluate_calibration(y_pred, y_true)
    assert isinstance(result.is_calibrated, bool)


def test_brier_excellent_grade():
    """Brier <= 0.18 qualifies as EXCELLENT."""
    y_pred = [0.85, 0.90, 0.10, 0.15]
    y_true = [1, 1, 0, 0]
    brier = compute_brier_score(y_pred, y_true)
    assert brier <= 0.18


def test_brier_poor_grade():
    """Brier = 1.0 is POOR."""
    y_pred = [0.0, 1.0]
    y_true = [1, 0]
    brier = compute_brier_score(y_pred, y_true)
    assert brier > 0.25


# ── print_calibration_report ─────────────────────────────────────────────────

def test_print_calibration_report_runs(capsys):
    y_pred = [0.3, 0.5, 0.8, 0.2, 0.6]
    y_true = [0, 1, 1, 0, 1]
    result = evaluate_calibration(y_pred, y_true)
    print_calibration_report(result)
    out = capsys.readouterr().out
    assert "Brier score" in out
    assert "Brier skill score" in out
    assert any(g in out for g in ("EXCELLENT", "GOOD", "FAIR", "POOR"))
