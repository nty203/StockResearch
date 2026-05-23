"""Paper trading 신호 생성기.

매일 스캐너가 탐지한 CategoryMatch를 paper_trades 테이블에 기록하고
Telegram으로 매수/매도 신호를 발송.

실제 자동매매는 아님 — 수동 체결 후 paper_trades에 실제 체결가 업데이트 필요.

흐름:
  1. 스캐너 완료 후 이 모듈 호출
  2. entry_filter 통과 종목 → "BUY_SIGNAL" 생성
  3. 기존 보유 포지션에 exit_rules 적용 → "EXIT_SIGNAL" 생성
  4. Telegram 알림 + paper_trades DB 기록
  5. 주간 리포트: 실현 P&L, 미실현 P&L, 최대 낙폭
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class PaperSignal:
    signal_type: str        # "BUY_SIGNAL" | "EXIT_SIGNAL" | "WATCH"
    ticker: str
    category: str
    confidence: float
    suggested_price: float  # 제안 체결가 (당일 종가)
    suggested_size_pct: float  # 포트폴리오 대비 비중 제안
    reason: str
    signal_date: str        # "YYYY-MM-DD"
    entry_details: dict = field(default_factory=dict)


def generate_daily_signals(
    client,
    scan_date: str | None = None,
    portfolio_value: float = 100_000_000,
) -> list[PaperSignal]:
    """오늘 스캔 결과에서 paper trading 신호 생성."""
    from ..trading.entry_filter import check_entry
    from ..trading.exit_rules import check_exit, Position
    from ..trading.position_sizer import compute_position_size

    today = scan_date or date.today().isoformat()
    signals: list[PaperSignal] = []

    # 1. 오늘 스캔된 CategoryMatch 로드
    try:
        matches = (
            client.table("hundredx_category_matches")
            .select("ticker, category, confidence, evidence, detected_at, first_detected_at")
            .gte("detected_at", f"{today}T00:00:00")
            .is_("exited_at", "null")
            .order("confidence", desc=True)
            .limit(50)
            .execute()
            .data or []
        )
    except Exception as e:
        logger.warning("Failed to load category matches: %s", e)
        matches = []

    # 2. 현재 paper portfolio 로드
    try:
        existing_positions = (
            client.table("paper_trades")
            .select("*")
            .eq("status", "open")
            .execute()
            .data or []
        )
    except Exception as e:
        logger.warning("Failed to load paper trades: %s", e)
        existing_positions = []

    open_tickers = {p["ticker"] for p in existing_positions}

    # 3. 신규 매수 신호 생성
    for m in matches:
        ticker = m["ticker"]
        category = m["category"]
        confidence = float(m.get("confidence", 0))

        # 이미 보유 중이면 skip
        if ticker in open_tickers:
            continue

        # 최소 신뢰도 체크
        if confidence < 0.75:
            continue

        # stock_data 조회 (간단버전 — 실제는 재무 데이터 join 필요)
        stock_data = {"market": "KOSPI"}  # 기본값

        entry = check_entry(
            ticker=ticker,
            category=category,
            confidence=confidence,
            stock_data=stock_data,
            portfolio_state={"n_positions": len(open_tickers), "max_positions": 15},
            min_confidence=0.75,
            require_momentum=False,   # paper trading에서는 momentum filter 느슨하게
            require_regime=False,
        )

        sizing = compute_position_size(
            category=category,
            confidence=confidence,
            ann_vol=0.40,
            portfolio_value=portfolio_value,
            n_current_positions=len(open_tickers),
        )

        sig = PaperSignal(
            signal_type="BUY_SIGNAL" if entry.should_buy else "WATCH",
            ticker=ticker,
            category=category,
            confidence=confidence,
            suggested_price=0.0,  # 당일 종가로 채워짐
            suggested_size_pct=sizing.weight,
            reason=entry.reason,
            signal_date=today,
            entry_details=entry.details,
        )
        signals.append(sig)

    # 4. 기존 포지션 exit 신호
    for pos_row in existing_positions:
        ticker = pos_row["ticker"]
        entry_price = float(pos_row.get("entry_price", 0))
        entry_date = str(pos_row.get("entry_date", today))
        category = pos_row.get("category", "미분류")
        confidence = float(pos_row.get("current_confidence", 0.75))
        current_price = float(pos_row.get("last_price", entry_price))

        pos = Position(
            ticker=ticker, category=category,
            entry_price=entry_price, entry_date=entry_date,
            shares=float(pos_row.get("shares", 0)),
            max_close_since_entry=float(pos_row.get("max_close_since_entry", current_price)),
            current_confidence=confidence,
        )
        action = check_exit(pos, current_price, today)

        if action.action != "hold":
            signals.append(PaperSignal(
                signal_type="EXIT_SIGNAL",
                ticker=ticker,
                category=category,
                confidence=confidence,
                suggested_price=current_price,
                suggested_size_pct=action.sell_fraction,
                reason=action.reason,
                signal_date=today,
                entry_details=action.details,
            ))

    # 5. DB 저장 + Telegram 알림
    if signals:
        _save_signals(client, signals)
        _send_telegram_alerts(signals)

    return signals


def _save_signals(client, signals: list[PaperSignal]) -> None:
    rows = [
        {
            "signal_date": s.signal_date,
            "signal_type": s.signal_type,
            "ticker": s.ticker,
            "category": s.category,
            "confidence": s.confidence,
            "suggested_size_pct": s.suggested_size_pct,
            "reason": s.reason,
            "details": s.entry_details,
            "status": "pending",  # 수동 체결 전
        }
        for s in signals
    ]
    try:
        client.table("paper_trade_signals").insert(rows).execute()
    except Exception as e:
        logger.warning("Failed to save signals: %s", e)


def _send_telegram_alerts(signals: list[PaperSignal]) -> None:
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not bot_token or not chat_id:
        return

    buy_signals = [s for s in signals if s.signal_type == "BUY_SIGNAL"]
    exit_signals = [s for s in signals if s.signal_type == "EXIT_SIGNAL"]

    msgs = []
    if buy_signals:
        lines = "\n".join(
            f"  🟢 {s.ticker} | {s.category} | conf={s.confidence:.2f} | size={s.suggested_size_pct:.1%}"
            for s in buy_signals[:5]
        )
        msgs.append(f"[Paper] 매수 신호 {len(buy_signals)}개\n{lines}")

    if exit_signals:
        lines = "\n".join(
            f"  🔴 {s.ticker} | {s.reason}"
            for s in exit_signals[:5]
        )
        msgs.append(f"[Paper] 매도 신호 {len(exit_signals)}개\n{lines}")

    import urllib.request, json
    for msg in msgs:
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = json.dumps({"chat_id": chat_id, "text": msg}).encode()
        try:
            urllib.request.urlopen(
                urllib.request.Request(url, data=payload,
                                       headers={"Content-Type": "application/json"}),
                timeout=10,
            )
        except Exception as e:
            logger.warning("Telegram send failed: %s", e)


def generate_weekly_report(client) -> dict:
    """주간 paper trading 성과 리포트."""
    week_ago = (date.today() - timedelta(days=7)).isoformat()
    try:
        closed = (
            client.table("paper_trades")
            .select("*")
            .eq("status", "closed")
            .gte("exit_date", week_ago)
            .execute()
            .data or []
        )
    except Exception as e:
        logger.warning("Failed to load closed trades: %s", e)
        return {}

    if not closed:
        return {"week_trades": 0, "week_return": 0.0}

    returns = [
        (float(t.get("exit_price", 0)) / float(t.get("entry_price", 1)) - 1)
        for t in closed
        if float(t.get("entry_price", 0)) > 0
    ]
    wins = [r for r in returns if r > 0]
    losses = [r for r in returns if r <= 0]

    return {
        "week_trades": len(closed),
        "week_win_rate": len(wins) / len(returns) if returns else 0,
        "week_avg_return": sum(returns) / len(returns) if returns else 0,
        "week_best": max(returns) if returns else 0,
        "week_worst": min(returns) if returns else 0,
    }
