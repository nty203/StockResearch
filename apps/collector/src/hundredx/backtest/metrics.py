"""백테스트 성과 메트릭.

필수 메트릭:
  - Annualized return (net of costs & taxes)
  - Sharpe ratio (annualized)
  - Sortino ratio
  - Max drawdown (peak-to-trough)
  - Calmar ratio (return / |MDD|)
  - Win rate, Avg R-multiple
  - Brier score (confidence calibration)

핵심 거버넌스 메트릭:
  - Deflated Sharpe Ratio (Bailey & López de Prado, 2014)
    → multiple testing 보정. ≥ 0.95 목표
  - Probability of Backtest Overfitting (PBO)
    → ≤ 5% 목표

참고:
  Bailey & López de Prado, "The Deflated Sharpe Ratio" (SSRN 2460551)
  Bailey et al., "The Probability of Backtest Overfitting" (SSRN 2326253)
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence


@dataclass
class BacktestMetrics:
    # Core performance
    total_return: float
    annualized_return: float
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown: float
    calmar_ratio: float
    # Trade stats
    n_trades: int
    win_rate: float
    avg_win_multiplier: float
    avg_loss_multiplier: float
    avg_r_multiple: float       # avg_win / avg_loss
    # Risk
    ann_volatility: float
    beta: float
    # Calibration
    brier_score: float
    # Governance
    deflated_sharpe: float
    pbo: float                  # Probability of Backtest Overfitting (0–1)
    # Meta
    n_days: int
    start_date: str
    end_date: str
    notes: str = ""


def compute_annualized_return(daily_returns: list[float]) -> float:
    """기하평균 연환산 수익률."""
    if not daily_returns:
        return 0.0
    cumulative = 1.0
    for r in daily_returns:
        cumulative *= (1 + r)
    n = len(daily_returns)
    return (cumulative ** (252 / n)) - 1


def compute_sharpe(
    daily_returns: list[float],
    risk_free_daily: float = 0.0,
) -> float:
    """Annualized Sharpe ratio."""
    n = len(daily_returns)
    if n < 2:
        return 0.0
    excess = [r - risk_free_daily for r in daily_returns]
    mean = sum(excess) / n
    std = math.sqrt(sum((r - mean) ** 2 for r in excess) / (n - 1))
    if std == 0:
        return 0.0
    return mean * math.sqrt(252) / (std * math.sqrt(252)) * math.sqrt(252)
    # 단순화: (mean_daily - rf_daily) / std_daily * sqrt(252)


def compute_sharpe_v2(daily_returns: list[float], risk_free_annual: float = 0.035) -> float:
    """Annualized Sharpe (올바른 공식)."""
    n = len(daily_returns)
    if n < 2:
        return 0.0
    rf_daily = (1 + risk_free_annual) ** (1 / 252) - 1
    excess = [r - rf_daily for r in daily_returns]
    mean = sum(excess) / n
    std = math.sqrt(sum((r - mean) ** 2 for r in excess) / (n - 1))
    return (mean / std) * math.sqrt(252) if std > 0 else 0.0


def compute_sortino(
    daily_returns: list[float],
    target_return: float = 0.0,
) -> float:
    """Annualized Sortino ratio (downside deviation only)."""
    n = len(daily_returns)
    if n < 2:
        return 0.0
    mean_excess = (sum(daily_returns) / n) - target_return
    neg = [r - target_return for r in daily_returns if r < target_return]
    if not neg:
        return float("inf")
    downside_std = math.sqrt(sum(r ** 2 for r in neg) / len(neg))
    return (mean_excess / downside_std) * math.sqrt(252) if downside_std > 0 else 0.0


def compute_max_drawdown(equity_curve: list[float]) -> float:
    """Peak-to-trough max drawdown (음수 반환, 예: -0.25 = -25%)."""
    if not equity_curve:
        return 0.0
    peak = equity_curve[0]
    mdd = 0.0
    for val in equity_curve:
        if val > peak:
            peak = val
        dd = (val - peak) / peak if peak > 0 else 0.0
        if dd < mdd:
            mdd = dd
    return mdd


def compute_win_rate_and_r(
    entry_prices: list[float],
    exit_prices: list[float],
) -> tuple[float, float, float, float]:
    """win_rate, avg_win_mult, avg_loss_mult, avg_r_multiple."""
    if not entry_prices:
        return 0.0, 0.0, 0.0, 0.0
    multiples = [e / p for p, e in zip(entry_prices, exit_prices) if p > 0]
    wins = [m for m in multiples if m >= 1.0]
    losses = [m for m in multiples if m < 1.0]
    win_rate = len(wins) / len(multiples) if multiples else 0.0
    avg_win = sum(wins) / len(wins) if wins else 1.0
    avg_loss = sum(losses) / len(losses) if losses else 1.0
    r_mult = (avg_win - 1) / (1 - avg_loss) if avg_loss < 1 else float("inf")
    return win_rate, avg_win, avg_loss, r_mult


# ── Deflated Sharpe Ratio ──────────────────────────────────────────────────

def compute_deflated_sharpe(
    sharpe_observed: float,
    n_trials: int,          # 테스트한 전략 수 (파라미터 조합 수)
    n_observations: int,    # 일별 수익률 개수
    skewness: float = 0.0,
    kurtosis: float = 3.0,
) -> float:
    """Deflated Sharpe Ratio (Bailey & López de Prado, 2014).

    SR* = (SR_observed - E[max SR]) / std(SR_under_H0)

    단순화 버전 (Full 구현은 scipy 없이도 가능):
    E[max SR] ≈ (1 - gamma) × Z^{-1}(1 - 1/N) + gamma × Z^{-1}(1 - 1/(N×e))
    여기서 gamma = Euler-Mascheroni constant ≈ 0.5772

    N = n_trials.
    """
    if n_observations < 2 or n_trials < 1:
        return sharpe_observed

    # Expected max Sharpe under H0 (trials 개수 기반)
    # 단순 근사: E[max Z-score] ≈ sqrt(2 × log(n_trials))
    z_max = math.sqrt(2 * math.log(max(n_trials, 1)))
    # 연환산 SR로 변환
    expected_max_sr = z_max / math.sqrt(n_observations / 252)

    # SR Variance 보정 (Mertens 2002)
    sr_var = ((1 - skewness * sharpe_observed +
               ((kurtosis - 1) / 4) * sharpe_observed ** 2)
              / (n_observations / 252))
    sr_std = math.sqrt(max(sr_var, 1e-10))

    deflated = (sharpe_observed - expected_max_sr) / sr_std
    return round(deflated, 4)


# ── Probability of Backtest Overfitting ────────────────────────────────────

def compute_pbo(
    is_oos_rank_above_median: list[bool],
) -> float:
    """Probability of Backtest Overfitting (simple estimator).

    López de Prado simplification:
    PBO = fraction of trials where IS best ≠ OOS best.

    완전 구현은 combinatorial cross-validation이 필요하나,
    여기서는 단순 버전: walk-forward fold별로 IS Sharpe 1위 → OOS 성과 확인.

    is_oos_rank_above_median: 각 fold에서 IS 최고 전략이 OOS median을 상회하는가?
    """
    if not is_oos_rank_above_median:
        return 0.5
    # PBO = P(IS 1위가 OOS에서 median 이하)
    pbo = 1.0 - sum(is_oos_rank_above_median) / len(is_oos_rank_above_median)
    return round(pbo, 4)


# ── 통합 평가 ──────────────────────────────────────────────────────────────

def evaluate(
    daily_returns: list[float],
    equity_curve: list[float],
    entry_prices: list[float],
    exit_prices: list[float],
    confidence_scores: list[float],
    actual_5x_labels: list[int],
    start_date: str,
    end_date: str,
    n_trials: int = 1,
    risk_free_annual: float = 0.035,
) -> BacktestMetrics:
    """전체 백테스트 성과 평가."""
    ann_ret = compute_annualized_return(daily_returns)
    sharpe = compute_sharpe_v2(daily_returns, risk_free_annual)
    sortino = compute_sortino(daily_returns)
    mdd = compute_max_drawdown(equity_curve)
    calmar = ann_ret / abs(mdd) if mdd < 0 else float("inf")
    win_rate, avg_win, avg_loss, r_mult = compute_win_rate_and_r(entry_prices, exit_prices)

    n = len(daily_returns)
    ann_vol = math.sqrt(sum(r**2 for r in daily_returns) / n * 252) if n > 0 else 0.0

    # Calibration
    brier = 0.25
    if confidence_scores and actual_5x_labels:
        from ..ml.calibration import compute_brier_score
        brier = compute_brier_score(confidence_scores, actual_5x_labels)

    # Governance
    # Skewness, kurtosis 근사
    mean_r = sum(daily_returns) / n if n > 0 else 0.0
    std_r = math.sqrt(sum((r - mean_r)**2 for r in daily_returns) / max(n-1, 1))
    skew = (sum((r - mean_r)**3 for r in daily_returns) / n) / (std_r**3 + 1e-10) if std_r > 0 else 0.0
    kurt = (sum((r - mean_r)**4 for r in daily_returns) / n) / (std_r**4 + 1e-10) if std_r > 0 else 3.0

    deflated = compute_deflated_sharpe(sharpe, n_trials, n, skew, kurt)
    # PBO: 단순 placeholder (walk-forward fold 결과 없으면 0.5)
    pbo = 0.5

    return BacktestMetrics(
        total_return=round((equity_curve[-1] / equity_curve[0] - 1) if equity_curve else 0.0, 4),
        annualized_return=round(ann_ret, 4),
        sharpe_ratio=round(sharpe, 3),
        sortino_ratio=round(sortino, 3),
        max_drawdown=round(mdd, 4),
        calmar_ratio=round(calmar, 3),
        n_trades=len(entry_prices),
        win_rate=round(win_rate, 4),
        avg_win_multiplier=round(avg_win, 4),
        avg_loss_multiplier=round(avg_loss, 4),
        avg_r_multiple=round(r_mult, 3),
        ann_volatility=round(ann_vol, 4),
        beta=0.0,  # 별도 계산 필요
        brier_score=round(brier, 4),
        deflated_sharpe=deflated,
        pbo=pbo,
        n_days=n,
        start_date=start_date,
        end_date=end_date,
    )


def print_metrics_report(m: BacktestMetrics) -> None:
    """콘솔 출력."""
    gate = (
        "✅ PASS (Sharpe≥1.5, MDD≤25%, DSR≥0.95)"
        if m.sharpe_ratio >= 1.5 and m.max_drawdown >= -0.25 and m.deflated_sharpe >= 0.95
        else "❌ FAIL"
    )
    print(f"\n=== Backtest Metrics ({m.start_date} ~ {m.end_date}) ===")
    print(f"Gate: {gate}")
    print(f"Total return:       {m.total_return:>+8.1%}")
    print(f"Annualized return:  {m.annualized_return:>+8.1%}  (target ≥ 25%)")
    print(f"Sharpe ratio:       {m.sharpe_ratio:>8.3f}  (target ≥ 1.5)")
    print(f"Sortino ratio:      {m.sortino_ratio:>8.3f}  (target ≥ 2.0)")
    print(f"Max drawdown:       {m.max_drawdown:>8.1%}  (target ≥ -25%)")
    print(f"Calmar ratio:       {m.calmar_ratio:>8.3f}  (target ≥ 1.0)")
    print(f"Win rate:           {m.win_rate:>8.1%}")
    print(f"Avg R-multiple:     {m.avg_r_multiple:>8.2f}x  (target ≥ 2.5x)")
    print(f"Ann. volatility:    {m.ann_volatility:>8.1%}")
    print(f"Brier score:        {m.brier_score:>8.4f}  (target ≤ 0.18)")
    print(f"Deflated Sharpe:    {m.deflated_sharpe:>8.4f}  (target ≥ 0.95)")
    print(f"PBO:                {m.pbo:>8.1%}  (target ≤ 5%)")
    print(f"Trades:             {m.n_trades:>8d}")
