"""Tests for backtest.metrics -- Sharpe, MDD, Deflated Sharpe, etc."""
import math
import pytest
from src.hundredx.backtest.metrics import (
    compute_annualized_return,
    compute_sharpe_v2,
    compute_sortino,
    compute_max_drawdown,
    compute_win_rate_and_r,
    compute_deflated_sharpe,
    compute_pbo,
    evaluate,
    BacktestMetrics,
    print_metrics_report,
)


# ── compute_annualized_return ────────────────────────────────────────────────

def test_annualized_return_empty():
    assert compute_annualized_return([]) == 0.0


def test_annualized_return_flat():
    returns = [0.0] * 252
    assert abs(compute_annualized_return(returns)) < 1e-9


def test_annualized_return_10pct():
    r_daily = (1.10) ** (1 / 252) - 1
    returns = [r_daily] * 252
    result = compute_annualized_return(returns)
    assert abs(result - 0.10) < 1e-6


def test_annualized_return_negative():
    r_daily = (0.80) ** (1 / 252) - 1
    returns = [r_daily] * 252
    result = compute_annualized_return(returns)
    assert result < 0


# ── compute_sharpe_v2 ─────────────────────────────────────────────────────────

def test_sharpe_empty():
    assert compute_sharpe_v2([]) == 0.0


def test_sharpe_zero_variance():
    # All same returns -> std=0 -> Sharpe=0
    returns = [0.001] * 100
    assert compute_sharpe_v2(returns) == 0.0


def test_sharpe_positive_for_good_strategy():
    import random
    random.seed(42)
    returns = [0.001 + random.gauss(0, 0.0002) for _ in range(500)]
    sharpe = compute_sharpe_v2(returns)
    assert sharpe > 1.0


def test_sharpe_negative_for_bad_strategy():
    import random
    random.seed(42)
    returns = [-0.002 + random.gauss(0, 0.001) for _ in range(252)]
    sharpe = compute_sharpe_v2(returns)
    assert sharpe < 0


# ── compute_sortino ────────────────────────────────────────────────────────────

def test_sortino_empty():
    assert compute_sortino([]) == 0.0


def test_sortino_no_negative_returns():
    returns = [0.001] * 252
    result = compute_sortino(returns)
    assert result == float("inf")


def test_sortino_positive_for_profitable():
    import random
    random.seed(42)
    returns = [0.001 + random.gauss(0, 0.003) for _ in range(500)]
    sortino = compute_sortino(returns)
    assert sortino > 0


# ── compute_max_drawdown ────────────────────────────────────────────────────

def test_mdd_empty():
    assert compute_max_drawdown([]) == 0.0


def test_mdd_monotone_growth():
    equity = [100, 110, 120, 130, 140]
    assert compute_max_drawdown(equity) == 0.0


def test_mdd_known_drawdown():
    # Peak at 200, trough at 150 -> MDD = (150-200)/200 = -25%
    equity = [100, 150, 200, 160, 150, 180, 200]
    mdd = compute_max_drawdown(equity)
    assert abs(mdd - (-0.25)) < 1e-9


def test_mdd_always_negative_or_zero():
    import random
    random.seed(42)
    equity = [100]
    for _ in range(100):
        equity.append(equity[-1] * (1 + random.gauss(0, 0.02)))
    assert compute_max_drawdown(equity) <= 0.0


def test_mdd_single_element():
    assert compute_max_drawdown([100]) == 0.0


# ── compute_win_rate_and_r ──────────────────────────────────────────────────

def test_win_rate_all_wins():
    entries = [100, 100, 100]
    exits = [200, 150, 300]
    wr, avg_win, avg_loss, r = compute_win_rate_and_r(entries, exits)
    assert wr == 1.0
    assert r == float("inf")  # no losses


def test_win_rate_all_losses():
    entries = [100, 100, 100]
    exits = [80, 85, 90]
    wr, avg_win, avg_loss, r = compute_win_rate_and_r(entries, exits)
    assert wr == 0.0


def test_win_rate_mixed():
    entries = [100, 100]
    exits = [200, 80]  # 2x win, 0.8x loss
    wr, avg_win, avg_loss, r_mult = compute_win_rate_and_r(entries, exits)
    assert wr == 0.5
    assert abs(avg_win - 2.0) < 1e-9
    assert abs(avg_loss - 0.8) < 1e-9
    # r = (2.0-1)/(1-0.8) = 1/0.2 = 5
    assert abs(r_mult - 5.0) < 1e-9


def test_win_rate_empty():
    wr, avg_win, avg_loss, r = compute_win_rate_and_r([], [])
    assert wr == 0.0


# ── compute_deflated_sharpe ─────────────────────────────────────────────────

def test_deflated_sharpe_single_trial_positive():
    """With n_trials=1, DSR should be positive for Sharpe > 0."""
    sr = 1.5
    dsr = compute_deflated_sharpe(sr, n_trials=1, n_observations=252)
    assert dsr > 0


def test_deflated_sharpe_many_trials_penalized():
    """More trials -> higher expected max -> lower DSR."""
    sr = 2.0
    dsr_1 = compute_deflated_sharpe(sr, n_trials=1, n_observations=1000)
    dsr_100 = compute_deflated_sharpe(sr, n_trials=100, n_observations=1000)
    dsr_10000 = compute_deflated_sharpe(sr, n_trials=10000, n_observations=1000)
    assert dsr_1 >= dsr_100 >= dsr_10000


def test_deflated_sharpe_strong_signal_passes():
    """A very strong Sharpe with few trials should achieve DSR >= 0.95."""
    dsr = compute_deflated_sharpe(3.0, n_trials=5, n_observations=1000)
    assert dsr >= 0.95


def test_deflated_sharpe_edge_cases():
    assert compute_deflated_sharpe(1.5, n_trials=0, n_observations=1000) == 1.5
    assert compute_deflated_sharpe(1.5, n_trials=1, n_observations=0) == 1.5


# ── compute_pbo ─────────────────────────────────────────────────────────────

def test_pbo_all_above_median():
    assert compute_pbo([True, True, True, True, True]) == 0.0


def test_pbo_all_below_median():
    assert compute_pbo([False, False, False, False, False]) == 1.0


def test_pbo_half():
    assert compute_pbo([True, False, True, False]) == 0.5


def test_pbo_empty():
    assert compute_pbo([]) == 0.5


# ── evaluate (integration) ──────────────────────────────────────────────────

def _make_synthetic_data(n=500, ann_return=0.25):
    import random
    random.seed(42)
    daily_r = (1 + ann_return) ** (1 / 252) - 1
    returns = [daily_r + random.gauss(0, 0.015) for _ in range(n)]
    equity = [100_000_000]
    for r in returns:
        equity.append(equity[-1] * (1 + r))
    return returns, equity


def test_evaluate_returns_backtest_metrics():
    returns, equity = _make_synthetic_data()
    entries = [10_000] * 20
    exits = [15_000] * 15 + [8_000] * 5  # 75% win rate
    m = evaluate(
        daily_returns=returns,
        equity_curve=equity,
        entry_prices=entries,
        exit_prices=exits,
        confidence_scores=[0.85] * 20,
        actual_5x_labels=[1] * 10 + [0] * 10,
        start_date="2022-01-01",
        end_date="2023-12-31",
        n_trials=1,
    )
    assert isinstance(m, BacktestMetrics)
    assert m.sharpe_ratio > 0
    assert m.max_drawdown <= 0
    assert 0.0 <= m.win_rate <= 1.0
    assert m.n_trades == 20
    assert m.annualized_return > 0


def test_evaluate_mdd_in_range():
    returns, equity = _make_synthetic_data()
    m = evaluate(
        daily_returns=returns, equity_curve=equity,
        entry_prices=[100], exit_prices=[150],
        confidence_scores=[], actual_5x_labels=[],
        start_date="2022-01-01", end_date="2023-12-31",
    )
    assert -1.0 <= m.max_drawdown <= 0.0


# ── print_metrics_report ──────────────────────────────────────────────────────

def test_print_metrics_runs(capsys):
    returns, equity = _make_synthetic_data()
    m = evaluate(
        daily_returns=returns, equity_curve=equity,
        entry_prices=[10_000] * 10, exit_prices=[12_000] * 10,
        confidence_scores=[], actual_5x_labels=[],
        start_date="2022-01-01", end_date="2023-12-31",
    )
    print_metrics_report(m)
    out = capsys.readouterr().out
    assert "Sharpe ratio" in out
    assert "Max drawdown" in out
    assert ("PASS" in out or "FAIL" in out)
