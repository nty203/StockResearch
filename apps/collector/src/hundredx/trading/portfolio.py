"""포트폴리오 상태 관리.

- 보유 포지션 목록 관리
- 카테고리/섹터 집중도 추적
- 현금 비중 관리
- 일별 스냅샷 생성 (DB 저장용)
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Iterator

from .exit_rules import Position, ExitAction, check_exit, update_trailing_high
from .entry_filter import EntryDecision, check_entry
from .position_sizer import SizingResult, compute_position_size


@dataclass
class Trade:
    ticker: str
    category: str
    trade_date: str
    action: str          # "buy" | "sell_all" | "sell_partial"
    price: float
    shares: float
    value: float         # price × shares
    reason: str
    confidence: float = 0.0
    fees: float = 0.0    # 거래비용
    tax: float = 0.0     # 거래세


@dataclass
class PortfolioSnapshot:
    snapshot_date: str
    total_value: float
    cash: float
    equity_value: float
    n_positions: int
    positions: list[dict]          # [{ticker, category, weight, value, ...}]
    category_weights: dict[str, float]
    daily_return: float
    cumulative_return: float
    max_drawdown: float


class Portfolio:
    """포트폴리오 상태 관리자.

    사용법:
      pf = Portfolio(initial_cash=100_000_000)  # 1억
      pf.buy("005930", "수주잔고_선행", price=70000, shares=100, ...)
      pf.mark_to_market({"005930": 75000})  # 오늘 종가로 평가
      pf.snapshot("2024-01-15")
    """

    MAX_POSITIONS = 15
    MAX_CATEGORY_WEIGHT = 0.25
    MIN_CASH_RATIO = 0.10   # 항상 10% 이상 현금 유지

    def __init__(self, initial_cash: float = 100_000_000) -> None:
        self.cash = initial_cash
        self.initial_value = initial_cash
        self._positions: dict[str, Position] = {}   # ticker → Position
        self._current_prices: dict[str, float] = {}
        self._trade_log: list[Trade] = []
        self._snapshots: list[PortfolioSnapshot] = []
        self._peak_value = initial_cash

    # ── 매수/매도 ─────────────────────────────────────────────────────────

    def buy(
        self,
        ticker: str,
        category: str,
        price: float,
        shares: float,
        date_str: str,
        confidence: float = 0.75,
        reason: str = "signal",
        fees: float = 0.0,
        tax: float = 0.0,
    ) -> Trade | None:
        """매수 실행.

        Returns Trade 또는 None (현금 부족 등).
        """
        cost = price * shares + fees + tax
        if cost > self.cash:
            return None  # 현금 부족

        if ticker in self._positions:
            return None  # 이미 보유 중 (add-to-position은 별도 구현)

        self.cash -= cost
        self._positions[ticker] = Position(
            ticker=ticker,
            category=category,
            entry_price=price,
            entry_date=date_str,
            shares=shares,
            max_close_since_entry=price,
            current_confidence=confidence,
        )
        self._current_prices[ticker] = price

        trade = Trade(
            ticker=ticker, category=category, trade_date=date_str,
            action="buy", price=price, shares=shares,
            value=price * shares, reason=reason,
            confidence=confidence, fees=fees, tax=tax,
        )
        self._trade_log.append(trade)
        return trade

    def sell(
        self,
        ticker: str,
        price: float,
        date_str: str,
        fraction: float = 1.0,
        reason: str = "exit",
        fees: float = 0.0,
        tax: float = 0.0,
    ) -> Trade | None:
        """매도 실행.

        fraction=1.0 → 전량, 0.5 → 반매도.
        """
        if ticker not in self._positions:
            return None
        pos = self._positions[ticker]
        sell_shares = pos.shares * fraction
        proceeds = price * sell_shares - fees - tax
        self.cash += proceeds

        trade = Trade(
            ticker=ticker,
            category=pos.category,
            trade_date=date_str,
            action="sell_all" if fraction >= 1.0 else "sell_partial",
            price=price,
            shares=sell_shares,
            value=price * sell_shares,
            reason=reason,
            fees=fees,
            tax=tax,
        )
        self._trade_log.append(trade)

        if fraction >= 1.0:
            del self._positions[ticker]
            self._current_prices.pop(ticker, None)
        else:
            pos.shares -= sell_shares

        return trade

    # ── 일별 업데이트 ──────────────────────────────────────────────────────

    def mark_to_market(self, prices: dict[str, float]) -> None:
        """오늘 종가로 보유 포지션 평가 + trailing high 갱신."""
        for ticker, price in prices.items():
            if ticker in self._positions:
                self._current_prices[ticker] = price
                update_trailing_high(self._positions[ticker], price)

    def check_exits(
        self,
        current_date: str,
        atr_data: dict[str, float] | None = None,
        confidence_data: dict[str, float] | None = None,
        refutation_tickers: set[str] | None = None,
    ) -> list[tuple[str, ExitAction]]:
        """모든 포지션의 exit 신호 체크.

        Returns: [(ticker, ExitAction), ...]
        """
        signals = []
        atr_data = atr_data or {}
        confidence_data = confidence_data or {}
        refutation_tickers = refutation_tickers or set()

        for ticker, pos in list(self._positions.items()):
            current_price = self._current_prices.get(ticker, pos.entry_price)
            action = check_exit(
                pos=pos,
                current_price=current_price,
                current_date=current_date,
                atr_20d=atr_data.get(ticker),
                current_confidence=confidence_data.get(ticker),
                refutation_flag=ticker in refutation_tickers,
            )
            if action.action != "hold":
                signals.append((ticker, action))
        return signals

    # ── 집계 ───────────────────────────────────────────────────────────────

    @property
    def equity_value(self) -> float:
        return sum(
            self._current_prices.get(t, pos.entry_price) * pos.shares
            for t, pos in self._positions.items()
        )

    @property
    def total_value(self) -> float:
        return self.cash + self.equity_value

    @property
    def n_positions(self) -> int:
        return len(self._positions)

    def category_weights(self) -> dict[str, float]:
        total = self.total_value
        if total <= 0:
            return {}
        weights: dict[str, float] = {}
        for t, pos in self._positions.items():
            price = self._current_prices.get(t, pos.entry_price)
            w = price * pos.shares / total
            weights[pos.category] = weights.get(pos.category, 0.0) + w
        return weights

    def portfolio_state_for_entry(self) -> dict:
        """check_entry에 넘길 portfolio_state dict."""
        cat_weights = self.category_weights()
        state: dict = {
            "n_positions": self.n_positions,
            "max_positions": self.MAX_POSITIONS,
            "cash_ratio": self.cash / max(self.total_value, 1.0),
        }
        for cat, w in cat_weights.items():
            state[f"category_weight_{cat}"] = w
        state["max_category_weight"] = self.MAX_CATEGORY_WEIGHT
        return state

    def snapshot(self, snap_date: str) -> PortfolioSnapshot:
        """일별 스냅샷 생성."""
        total = self.total_value
        prev_total = self._snapshots[-1].total_value if self._snapshots else self.initial_value
        daily_ret = (total - prev_total) / prev_total if prev_total > 0 else 0.0
        cum_ret = (total - self.initial_value) / self.initial_value

        # MDD 업데이트
        self._peak_value = max(self._peak_value, total)
        mdd = (total - self._peak_value) / self._peak_value if self._peak_value > 0 else 0.0

        positions = []
        for t, pos in self._positions.items():
            price = self._current_prices.get(t, pos.entry_price)
            val = price * pos.shares
            positions.append({
                "ticker": t,
                "category": pos.category,
                "entry_price": pos.entry_price,
                "current_price": price,
                "shares": pos.shares,
                "value": round(val, 0),
                "weight": round(val / total, 4) if total > 0 else 0.0,
                "return": round(price / pos.entry_price - 1, 4) if pos.entry_price > 0 else 0.0,
                "days_held": (
                    datetime.fromisoformat(snap_date).date()
                    - datetime.fromisoformat(pos.entry_date).date()
                ).days,
                "confidence": pos.current_confidence,
            })

        snap = PortfolioSnapshot(
            snapshot_date=snap_date,
            total_value=round(total, 0),
            cash=round(self.cash, 0),
            equity_value=round(self.equity_value, 0),
            n_positions=self.n_positions,
            positions=positions,
            category_weights={k: round(v, 4) for k, v in self.category_weights().items()},
            daily_return=round(daily_ret, 6),
            cumulative_return=round(cum_ret, 6),
            max_drawdown=round(mdd, 6),
        )
        self._snapshots.append(snap)
        return snap

    def trades(self) -> list[Trade]:
        return list(self._trade_log)

    def performance_summary(self) -> dict:
        """간단한 성과 요약."""
        if not self._snapshots:
            return {}
        first = self._snapshots[0]
        last = self._snapshots[-1]
        rets = [s.daily_return for s in self._snapshots]

        import math
        n_days = len(rets)
        avg_ret = sum(rets) / n_days if n_days else 0.0
        std_ret = math.sqrt(sum((r - avg_ret) ** 2 for r in rets) / max(n_days - 1, 1))
        sharpe = (avg_ret * 252) / (std_ret * math.sqrt(252)) if std_ret > 0 else 0.0

        # Sortino (downside only)
        neg_rets = [r for r in rets if r < 0]
        downside_std = math.sqrt(sum(r**2 for r in neg_rets) / max(len(neg_rets), 1))
        sortino = (avg_ret * 252) / (downside_std * math.sqrt(252)) if downside_std > 0 else 0.0

        mdd = min(s.max_drawdown for s in self._snapshots)
        ann_ret = last.cumulative_return  # 간단 근사 (정확히는 CAGR 계산 필요)

        return {
            "total_return": round(last.cumulative_return, 4),
            "annualized_return": round(ann_ret, 4),
            "sharpe_ratio": round(sharpe, 3),
            "sortino_ratio": round(sortino, 3),
            "max_drawdown": round(mdd, 4),
            "calmar_ratio": round(ann_ret / abs(mdd), 3) if mdd < 0 else float("inf"),
            "n_trades": len(self._trade_log),
            "n_snapshots": len(self._snapshots),
        }
