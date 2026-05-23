"""3-tier exit rules — trailing ATR stop / hard stop / time stop.

Tier 1 — Trailing ATR stop (손절선이 주가 따라 올라감)
  - exit_price = max_close_since_entry × (1 - k × ATR_20d / close)
  - k=3 (default) → 변동성 3배 허용

Tier 2 — Hard stop (절대 하한선)
  - -20% from entry
  - PPTR confidence < 0.5 (시그널 붕괴)
  - Refutation flag 발생 (massive dilution / restatement / debt spike)

Tier 3 — Time stop (시간 기반 청산)
  - 12개월 내 2x 미달성: 50% 부분 청산
  - 24개월 내 2x 미달성: 전량 청산

Usage:
  pos = Position(ticker="005930", entry_price=50000, entry_date="2024-01-15", ...)
  action = check_exit(pos, current_price=60000, current_date="2024-06-01", ...)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta


@dataclass
class Position:
    ticker: str
    category: str
    entry_price: float
    entry_date: str          # "YYYY-MM-DD"
    shares: float            # 보유 주수 또는 비중
    max_close_since_entry: float = 0.0   # trailing high (매일 갱신)
    current_confidence: float = 0.75     # 최근 PPTR confidence
    notes: str = ""


@dataclass
class ExitAction:
    action: str              # "hold" | "sell_all" | "sell_partial"
    sell_fraction: float     # 0.0=hold, 0.5=반매도, 1.0=전량
    reason: str
    exit_tier: int           # 1=trailing, 2=hard, 3=time
    stop_price: float = 0.0
    details: dict = field(default_factory=dict)


def check_exit(
    pos: Position,
    current_price: float,
    current_date: str,
    atr_20d: float | None = None,
    current_confidence: float | None = None,
    refutation_flag: bool = False,
    *,
    # Tier 1 params
    atr_multiplier: float = 3.0,
    # Tier 2 params
    hard_stop_pct: float = -0.20,
    min_confidence: float = 0.50,
    # Tier 3 params
    time_stop_12m_target_x: float = 2.0,
    time_stop_24m_target_x: float = 2.0,
) -> ExitAction:
    """현재 포지션에 exit 신호 발생 여부 확인.

    Args:
        pos: 보유 포지션
        current_price: 현재가
        current_date: 오늘 날짜 "YYYY-MM-DD"
        atr_20d: 20일 ATR (없으면 Tier 1 skip)
        current_confidence: 최신 PPTR confidence (None이면 pos.current_confidence 사용)
        refutation_flag: dilution/restatement 등 반박 이벤트 발생
    """
    conf = current_confidence if current_confidence is not None else pos.current_confidence
    max_close = max(pos.max_close_since_entry, current_price)

    # 경과일 계산
    entry_dt = datetime.fromisoformat(pos.entry_date).date()
    curr_dt = datetime.fromisoformat(current_date).date()
    days_held = (curr_dt - entry_dt).days
    months_held = days_held / 30.44

    current_multiplier = current_price / pos.entry_price if pos.entry_price > 0 else 1.0
    details = {
        "days_held": days_held,
        "months_held": round(months_held, 1),
        "current_multiplier": round(current_multiplier, 3),
        "confidence": round(conf, 3),
    }

    # ── Tier 2: Hard stop (우선순위 높음) ────────────────────────────────
    return_from_entry = (current_price - pos.entry_price) / pos.entry_price
    if return_from_entry <= hard_stop_pct:
        return ExitAction(
            action="sell_all",
            sell_fraction=1.0,
            reason=f"hard_stop:{return_from_entry:.1%}<={hard_stop_pct:.0%}",
            exit_tier=2,
            stop_price=pos.entry_price * (1 + hard_stop_pct),
            details={**details, "return_from_entry": round(return_from_entry, 4)},
        )

    if conf < min_confidence:
        return ExitAction(
            action="sell_all",
            sell_fraction=1.0,
            reason=f"signal_decay:confidence={conf:.3f}<{min_confidence}",
            exit_tier=2,
            stop_price=current_price,
            details=details,
        )

    if refutation_flag:
        return ExitAction(
            action="sell_all",
            sell_fraction=1.0,
            reason="refutation_event",
            exit_tier=2,
            stop_price=current_price,
            details=details,
        )

    # ── Tier 1: Trailing ATR stop ─────────────────────────────────────────
    if atr_20d is not None and atr_20d > 0 and max_close > 0 and current_price > 0:
        atr_pct = atr_20d / current_price
        trailing_stop = max_close * (1 - atr_multiplier * atr_pct)
        details["trailing_stop"] = round(trailing_stop, 2)
        details["atr_pct"] = round(atr_pct, 4)
        if current_price <= trailing_stop:
            return ExitAction(
                action="sell_all",
                sell_fraction=1.0,
                reason=f"trailing_stop:{current_price:.0f}<={trailing_stop:.0f}",
                exit_tier=1,
                stop_price=trailing_stop,
                details=details,
            )

    # ── Tier 3: Time stop ─────────────────────────────────────────────────
    if months_held >= 24 and current_multiplier < time_stop_24m_target_x:
        return ExitAction(
            action="sell_all",
            sell_fraction=1.0,
            reason=f"time_stop_24m:{current_multiplier:.2f}x<{time_stop_24m_target_x}x",
            exit_tier=3,
            stop_price=current_price,
            details=details,
        )

    if months_held >= 12 and current_multiplier < time_stop_12m_target_x:
        return ExitAction(
            action="sell_partial",
            sell_fraction=0.5,
            reason=f"time_stop_12m_partial:{current_multiplier:.2f}x<{time_stop_12m_target_x}x",
            exit_tier=3,
            stop_price=current_price,
            details=details,
        )

    return ExitAction(
        action="hold",
        sell_fraction=0.0,
        reason="hold",
        exit_tier=0,
        details=details,
    )


def update_trailing_high(pos: Position, current_price: float) -> Position:
    """최고가 갱신 (매일 호출)."""
    if current_price > pos.max_close_since_entry:
        pos.max_close_since_entry = current_price
    return pos
