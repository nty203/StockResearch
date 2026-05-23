"""Event-driven backtester.

데이터 흐름:
  1. 날짜별 (bar-by-bar) 이벤트 처리
  2. PPTR signal → entry_filter → position_sizer → 매수
  3. 매일 mark-to-market → exit_rules 체크 → 매도
  4. 비용/세금 cost_model 적용
  5. PortfolioSnapshot 일별 기록
  6. BacktestMetrics 최종 계산

사용법:
  bt = Backtester(initial_cash=100_000_000, market="KOSPI")
  result = bt.run(signals, price_data, start="2019-07-01", end="2022-12-31")
  print_metrics_report(result.metrics)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Iterator

from .cost_model import compute_trade_cost
from .metrics import BacktestMetrics, evaluate, print_metrics_report
from ..trading.entry_filter import check_entry
from ..trading.exit_rules import check_exit, update_trailing_high, Position
from ..trading.position_sizer import compute_position_size
from ..trading.portfolio import Portfolio, Trade

logger = logging.getLogger(__name__)


@dataclass
class BacktestSignal:
    """단일 PPTR 시그널 (스캐너에서 생성)."""
    date: str           # "YYYY-MM-DD"
    ticker: str
    category: str
    confidence: float
    market: str         # "KOSPI" | "KOSDAQ" | "NYSE" | "NASDAQ"
    # 신호 생성 시점의 재무 데이터
    stock_data: dict = field(default_factory=dict)
    filings: list[dict] = field(default_factory=list)


@dataclass
class PriceBar:
    """일별 가격 데이터."""
    ticker: str
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    adv60: float = 0.0     # 60일 평균 거래대금
    atr_20d: float = 0.0   # 20일 ATR
    ma20: float = 0.0
    ma60: float = 0.0
    ma200: float = 0.0
    ann_vol: float = 0.0


@dataclass
class BacktestRun:
    """백테스트 실행 결과."""
    metrics: BacktestMetrics
    trades: list[Trade]
    snapshots: list[dict]
    n_signals_received: int
    n_signals_rejected: int
    rejection_reasons: dict[str, int]   # reason → count
    config: dict = field(default_factory=dict)


class Backtester:
    """PPTR 전략 event-driven backtester."""

    def __init__(
        self,
        initial_cash: float = 100_000_000,
        risk_free_annual: float = 0.035,
        min_confidence: float = 0.75,
        apply_capital_gains: bool = False,  # 소액 개인투자자 기본 False
        n_trials: int = 1,  # Deflated Sharpe 보정용
    ) -> None:
        self.initial_cash = initial_cash
        self.risk_free_annual = risk_free_annual
        self.min_confidence = min_confidence
        self.apply_capital_gains = apply_capital_gains
        self.n_trials = n_trials

    def run(
        self,
        signals: list[BacktestSignal],
        price_data: dict[str, dict[str, PriceBar]],  # ticker → date → PriceBar
        start: str,
        end: str,
        kospi_prices: dict[str, float] | None = None,   # 시장 지수 (regime filter)
        kospi_ma200: dict[str, float] | None = None,
    ) -> BacktestRun:
        """백테스트 실행.

        Args:
            signals: PPTR 시그널 목록 (날짜 오름차순 정렬)
            price_data: {ticker: {date: PriceBar}}
            start, end: "YYYY-MM-DD" 백테스트 기간
            kospi_prices: {date: index_close}
            kospi_ma200: {date: ma200_close}
        """
        portfolio = Portfolio(initial_cash=self.initial_cash)

        # 시그널을 날짜별로 인덱싱
        signals_by_date: dict[str, list[BacktestSignal]] = {}
        for sig in signals:
            if start <= sig.date <= end:
                signals_by_date.setdefault(sig.date, []).append(sig)

        n_received = 0
        n_rejected = 0
        rejection_reasons: dict[str, int] = {}

        daily_returns: list[float] = []
        equity_curve: list[float] = [self.initial_cash]
        entry_prices_log: list[float] = []
        exit_prices_log: list[float] = []
        confidence_log: list[float] = []
        label_log: list[int] = []  # 실제 5x 달성 여부 (post-hoc)

        # 날짜 순회
        current = date.fromisoformat(start)
        end_date = date.fromisoformat(end)

        while current <= end_date:
            date_str = current.isoformat()

            # ── 1. 오늘 종가로 포트폴리오 평가 ───────────────────────────
            today_prices: dict[str, float] = {}
            today_atr: dict[str, float] = {}
            for ticker in list(portfolio._positions.keys()):
                bar = (price_data.get(ticker) or {}).get(date_str)
                if bar:
                    today_prices[ticker] = bar.close
                    today_atr[ticker] = bar.atr_20d

            portfolio.mark_to_market(today_prices)

            # ── 2. Exit check ─────────────────────────────────────────────
            exit_signals = portfolio.check_exits(
                current_date=date_str,
                atr_data=today_atr,
            )
            for ticker, exit_action in exit_signals:
                if exit_action.action in ("sell_all", "sell_partial"):
                    pos = portfolio._positions.get(ticker)
                    price = today_prices.get(ticker, 0.0)
                    if price > 0 and pos:
                        bar = (price_data.get(ticker) or {}).get(date_str)
                        adv60 = bar.adv60 if bar else 0.0
                        mkt = pos.category  # 실제는 stock_data.market 필요

                        cost = compute_trade_cost(
                            price=price, shares=pos.shares * exit_action.sell_fraction,
                            market="KOSPI", adv60=adv60, side="sell",
                            entry_price=pos.entry_price,
                            apply_capital_gains=self.apply_capital_gains,
                        )
                        trade = portfolio.sell(
                            ticker=ticker,
                            price=cost.effective_price,
                            date_str=date_str,
                            fraction=exit_action.sell_fraction,
                            reason=exit_action.reason,
                            fees=cost.commission,
                            tax=cost.tax,
                        )
                        if trade:
                            exit_prices_log.append(cost.effective_price)

            # ── 3. 신규 시그널 처리 ───────────────────────────────────────
            for sig in (signals_by_date.get(date_str) or []):
                n_received += 1
                bar = (price_data.get(sig.ticker) or {}).get(date_str)
                if not bar or bar.close <= 0:
                    n_rejected += 1
                    rejection_reasons["no_price_data"] = rejection_reasons.get("no_price_data", 0) + 1
                    continue

                # Enrich stock_data with price info
                stock_data = {
                    **sig.stock_data,
                    "close": bar.close,
                    "ma20": bar.ma20, "ma60": bar.ma60, "ma200": bar.ma200,
                    "avg_daily_value_60d": bar.adv60,
                    "ann_vol_252d": bar.ann_vol,
                    "market": sig.market,
                    "kospi_close": (kospi_prices or {}).get(date_str, 0.0),
                    "kospi_ma200": (kospi_ma200 or {}).get(date_str, 0.0),
                }

                # Entry filter
                entry = check_entry(
                    ticker=sig.ticker,
                    category=sig.category,
                    confidence=sig.confidence,
                    stock_data=stock_data,
                    portfolio_state=portfolio.portfolio_state_for_entry(),
                    min_confidence=self.min_confidence,
                    target_position_value_krw=portfolio.total_value * 0.05,
                )

                if not entry.should_buy:
                    n_rejected += 1
                    r = entry.reason.split(":")[0]
                    rejection_reasons[r] = rejection_reasons.get(r, 0) + 1
                    continue

                # Position sizing
                cat_used = portfolio.portfolio_state_for_entry().get(
                    f"category_weight_{sig.category}", 0.0
                )
                sizing = compute_position_size(
                    category=sig.category,
                    confidence=sig.confidence,
                    ann_vol=bar.ann_vol or 0.40,  # 데이터 없으면 40% 가정
                    portfolio_value=portfolio.total_value,
                    current_price=bar.close,
                    category_used_weight=cat_used,
                    n_current_positions=portfolio.n_positions,
                )

                if sizing.weight <= 0 or sizing.shares <= 0:
                    n_rejected += 1
                    rejection_reasons["sizing_zero"] = rejection_reasons.get("sizing_zero", 0) + 1
                    continue

                # 거래비용
                cost = compute_trade_cost(
                    price=bar.close,
                    shares=sizing.shares,
                    market=sig.market,
                    adv60=bar.adv60,
                    side="buy",
                )

                # 매수
                trade = portfolio.buy(
                    ticker=sig.ticker,
                    category=sig.category,
                    price=cost.effective_price,
                    shares=float(sizing.shares),
                    date_str=date_str,
                    confidence=sig.confidence,
                    reason="pptr_signal",
                    fees=cost.commission,
                    tax=cost.tax,
                )
                if trade:
                    entry_prices_log.append(cost.effective_price)
                    confidence_log.append(sig.confidence)
                    logger.debug("BUY %s @ %.0f (conf=%.3f, size=%.1f%%)",
                                 sig.ticker, cost.effective_price, sig.confidence,
                                 sizing.weight * 100)

            # ── 4. 일별 스냅샷 ────────────────────────────────────────────
            snap = portfolio.snapshot(date_str)
            daily_returns.append(snap.daily_return)
            equity_curve.append(snap.total_value)

            current += timedelta(days=1)

        # ── 5. 성과 평가 ──────────────────────────────────────────────────
        metrics = evaluate(
            daily_returns=daily_returns,
            equity_curve=equity_curve,
            entry_prices=entry_prices_log,
            exit_prices=exit_prices_log,
            confidence_scores=confidence_log,
            actual_5x_labels=label_log,
            start_date=start,
            end_date=end,
            n_trials=self.n_trials,
            risk_free_annual=self.risk_free_annual,
        )

        return BacktestRun(
            metrics=metrics,
            trades=portfolio.trades(),
            snapshots=[s.__dict__ for s in portfolio._snapshots],
            n_signals_received=n_received,
            n_signals_rejected=n_rejected,
            rejection_reasons=rejection_reasons,
            config={
                "initial_cash": self.initial_cash,
                "min_confidence": self.min_confidence,
                "start": start,
                "end": end,
            },
        )

    def save_results(self, client, run: BacktestRun) -> None:
        """백테스트 결과 DB 저장."""
        try:
            from datetime import datetime, timezone
            m = run.metrics
            client.table("backtest_runs").insert({
                "run_at": datetime.now(timezone.utc).isoformat(),
                "start_date": m.start_date,
                "end_date": m.end_date,
                "n_days": m.n_days,
                "initial_cash": self.initial_cash,
                "total_return": m.total_return,
                "annualized_return": m.annualized_return,
                "sharpe_ratio": m.sharpe_ratio,
                "sortino_ratio": m.sortino_ratio,
                "max_drawdown": m.max_drawdown,
                "calmar_ratio": m.calmar_ratio,
                "win_rate": m.win_rate,
                "avg_r_multiple": m.avg_r_multiple,
                "brier_score": m.brier_score,
                "deflated_sharpe": m.deflated_sharpe,
                "pbo": m.pbo,
                "n_trades": m.n_trades,
                "n_signals_received": run.n_signals_received,
                "n_signals_rejected": run.n_signals_rejected,
                "rejection_reasons": run.rejection_reasons,
                "config": run.config,
                "passed_governance": (
                    m.sharpe_ratio >= 1.5
                    and m.max_drawdown >= -0.25
                    and m.deflated_sharpe >= 0.95
                ),
            }).execute()
        except Exception as e:
            logger.warning("Failed to save backtest results: %s", e)
