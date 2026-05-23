"""텔레그램 알림 유틸리티.

InfiniteTetrade 프로젝트와 동일한 방식 (HTML parse_mode, Bot API).
환경변수: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
"""
from __future__ import annotations

import logging
import os
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

_API_BASE = "https://api.telegram.org/bot{token}"

# 카테고리별 이모지
_CAT_EMOJI = {
    "빅테크_파트너":  "🤖",
    "임상_파이프라인": "💊",
    "공급_병목":      "⚡",
    "정책_수혜":      "🏛️",
    "수주잔고_선행":  "🚢",
    "수익성_급전환":  "📈",
    "플랫폼_독점":    "🔒",
    "단기_테마_급등": "🔥",
    "미분류":         "❓",
}


def _get_token_chat() -> tuple[str | None, str | None]:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    return (token or None, chat_id or None)


def send_message(text: str, parse_mode: str = "HTML", silent: bool = False) -> bool:
    """텔레그램 메시지 발송.

    Args:
        text: 발송할 텍스트
        parse_mode: "HTML" 또는 "Markdown"
        silent: True면 알림음 없이 발송

    Returns:
        발송 성공 여부
    """
    token, chat_id = _get_token_chat()
    if not token or not chat_id:
        logger.debug("TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set — skip notification")
        return False

    url = f"{_API_BASE.format(token=token)}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
        "disable_notification": silent,
        "disable_web_page_preview": True,
    }

    try:
        with httpx.Client(timeout=10) as client:
            resp = client.post(url, json=payload)
            if resp.status_code == 200:
                return True
            else:
                logger.warning("Telegram API error %d: %s", resp.status_code, resp.text[:200])
                return False
    except Exception as e:
        logger.warning("Telegram send failed: %s", e)
        return False


def is_enabled() -> bool:
    """텔레그램 알림 활성화 여부."""
    token, chat_id = _get_token_chat()
    return bool(token and chat_id)


# ── 알림 메시지 빌더들 ─────────────────────────────────────────────────────────

def notify_new_matches(new_matches: list[dict], total_scanned: int = 0) -> bool:
    """새로 탐지된 100배 후보 종목 알림.

    Args:
        new_matches: [{"ticker", "category", "confidence", "headline", "name"}]
        total_scanned: 전체 스캔 종목 수
    """
    if not new_matches:
        return False

    from datetime import date
    today = date.today().strftime("%Y-%m-%d")

    # 신뢰도 내림차순 정렬
    sorted_matches = sorted(new_matches, key=lambda x: -x.get("confidence", 0))

    lines = [f"🚨 <b>100배 신호 탐지</b> ({today})"]
    lines.append(f"신규 {len(new_matches)}개" + (f" / {total_scanned:,}개 스캔" if total_scanned else ""))
    lines.append("")

    for m in sorted_matches[:10]:  # 최대 10개
        ticker = m.get("ticker", "?")
        name = m.get("name", "")
        category = m.get("category", "?")
        conf = m.get("confidence", 0)
        headline = (m.get("headline") or m.get("evidence_summary") or "")[:60]

        emoji = _CAT_EMOJI.get(category, "📌")
        name_str = f" {name}" if name else ""
        conf_pct = f"{conf * 100:.0f}%"

        lines.append(f"{emoji} <b>{ticker}</b>{name_str}")
        lines.append(f"   {category} | 신뢰도 {conf_pct}")
        if headline:
            lines.append(f"   <i>{headline}</i>")
        lines.append("")

    return send_message("\n".join(lines))


def notify_scanner_summary(
    new_count: int,
    updated_count: int,
    total_active: int,
    elapsed_sec: float = 0,
    top_matches: Optional[list[dict]] = None,
) -> bool:
    """스캐너 실행 완료 요약 알림.

    새 탐지가 0개일 때도 일일 요약으로 발송.
    """
    from datetime import date
    today = date.today().strftime("%Y-%m-%d")
    elapsed_str = f" ({elapsed_sec:.0f}초)" if elapsed_sec else ""

    lines = [f"📊 <b>100배 스캐너 완료</b> ({today}){elapsed_str}"]
    lines.append(f"✨ 신규: <b>{new_count}</b>개  |  업데이트: {updated_count}개  |  활성: {total_active:,}개")

    if top_matches:
        lines.append("")
        lines.append("🏆 <b>상위 탐지 종목:</b>")
        for m in top_matches[:5]:
            ticker = m.get("ticker", "?")
            name = m.get("name", "")
            cat = m.get("category", "?")
            conf = m.get("confidence", 0)
            emoji = _CAT_EMOJI.get(cat, "📌")
            name_str = f" {name}" if name else ""
            lines.append(f"  {emoji} <b>{ticker}</b>{name_str} — {cat} {conf*100:.0f}%")

    return send_message("\n".join(lines))


def notify_filing_alert(filings: list[dict]) -> bool:
    """고가치 공시 수집 알림 (시간당 — 키워드 매칭 공시만).

    Args:
        filings: 수집된 공시 목록 (keywords, headline, ticker, filed_at 포함)
    """
    if not filings:
        return False

    from datetime import date
    today = date.today().strftime("%Y-%m-%d %H:%M")

    lines = [f"📋 <b>주요 공시 수집</b> ({today})"]
    lines.append(f"{len(filings)}건 탐지")
    lines.append("")

    for f in filings[:8]:  # 최대 8건
        ticker = f.get("ticker", "?")
        headline = (f.get("headline") or "")[:70]
        kws = f.get("keywords") or []
        kw_str = ", ".join(kws[:3]) if kws else ""
        filed = str(f.get("filed_at") or "")[:10]

        lines.append(f"📌 <b>{ticker}</b> [{filed}]")
        lines.append(f"   {headline}")
        if kw_str:
            lines.append(f"   🔑 {kw_str}")
        lines.append("")

    return send_message("\n".join(lines))


def notify_error(context: str, error: str) -> bool:
    """오류 알림."""
    lines = [
        "❌ <b>StockResearch 오류</b>",
        f"<b>위치:</b> {context}",
        f"<b>오류:</b> <code>{error[:300]}</code>",
    ]
    return send_message("\n".join(lines))
