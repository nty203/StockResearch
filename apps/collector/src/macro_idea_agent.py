"""Macro Idea Agent — 뉴스·DART 공시·가격 데이터를 Claude API로 분석해
투자 가설을 자동 도출하고 macro_ideas 테이블에 저장한다.

실행: uv run python -m src.macro_idea_agent
"""
import json
import logging
import os
from datetime import date, datetime, timedelta, timezone

import anthropic
import httpx

from .upsert import get_client, retry_execute

logger = logging.getLogger(__name__)

# ─── 1. 데이터 수집 ──────────────────────────────────────────────────────────

def _since(days: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")


def fetch_news_snapshot(client) -> dict:
    """macro_news + news(증권사) + DART 공시 + 테마 랭킹을 모아서 반환."""
    # macro_news 최근 3일
    macro = retry_execute(
        lambda: client.table("macro_news")
        .select("title,summary,category,published_at,source")
        .gte("published_at", _since(3))
        .order("published_at", desc=True)
        .limit(300)
        .execute()
    ).data or []

    # 빅테크발언 최근 7일
    bigtech = retry_execute(
        lambda: client.table("macro_news")
        .select("title,summary,published_at")
        .eq("category", "빅테크발언")
        .gte("published_at", _since(7))
        .order("published_at", desc=True)
        .limit(20)
        .execute()
    ).data or []

    # news (증권사 리포트) 최근 7일
    broker = retry_execute(
        lambda: client.table("news")
        .select("ticker,title,summary,published_at")
        .eq("lang", "ko")
        .gte("published_at", _since(7))
        .order("published_at", desc=True)
        .limit(120)
        .execute()
    ).data or []

    # DART 수주/계약 공시 최근 10일
    filings = retry_execute(
        lambda: client.table("filings")
        .select("ticker,headline,filed_at,parsed_amount,parsed_customer")
        .or_("headline.like.*수주*,headline.like.*공급계약*,headline.like.*MOU*,headline.like.*납품계약*")
        .gte("filed_at", _since(10))
        .order("filed_at", desc=True)
        .limit(30)
        .execute()
    ).data or []

    # macro_theme_ranks 최신
    theme_rows = retry_execute(
        lambda: client.table("macro_theme_ranks")
        .select("theme,rank,score,aligned,candidates")
        .order("rank")
        .limit(9)
        .execute()
    ).data or []

    return {
        "macro_news": macro,
        "bigtech": bigtech,
        "broker_reports": broker,
        "dart_filings": filings,
        "theme_ranks": theme_rows,
    }


def fetch_price(ticker: str, supabase_url: str, service_key: str) -> dict | None:
    """prices_daily에서 52주 데이터를 가져와 통계를 계산."""
    resp = httpx.get(
        f"{supabase_url}/rest/v1/prices_daily",
        params={"select": "close", "ticker": f"eq.{ticker}", "order": "date.desc", "limit": "250"},
        headers={"apikey": service_key, "Authorization": f"Bearer {service_key}"},
        timeout=10,
    )
    if resp.status_code != 200:
        return None
    rows = resp.json()
    if not rows:
        return None
    closes = [r["close"] for r in rows]
    c = closes[0]
    max52 = max(closes)
    r1 = round((c / closes[20] - 1) * 100, 1) if len(closes) > 20 else 0
    r3 = round((c / closes[60] - 1) * 100, 1) if len(closes) > 60 else 0
    n52 = round(c / max52 * 100, 1)
    pos = 50 if 85 <= n52 <= 95 else (40 if 95 < n52 <= 100 else (35 if 100 < n52 <= 112 else (25 if 70 <= n52 < 85 else 15)))
    pen = min(30, max(0, (r3 - 60) / 2))
    mom = min(5, r1) if r1 > 0 else 0
    early = round(pos - pen + mom, 1)
    flag = "🌐선행" if n52 >= 95 else ("🔺임박" if 85 <= n52 < 95 else ("📌후행" if 70 <= n52 < 85 else "❄️침체"))
    return {"near_52w_high": n52, "ret_1m": r1, "ret_3m": r3, "early_signal_score": early, "signal_flag": flag}


# ─── 2. Claude API 호출 ──────────────────────────────────────────────────────

SYSTEM_PROMPT = """당신은 대한민국 주식시장 탑티어 투자전략가 시스템이다.
주어진 뉴스·공시·테마 랭킹 데이터를 분석해 **오르기 전에 찾는** 투자 가설을 도출한다.

핵심 원칙:
1. 뉴스 우선 — 반드시 뉴스/공시 → 가설 → 종목 순서. 역방향 금지.
2. 조기 신호 우선 — 증권사 목표가 상향은 후행 신호. 진짜 선행 신호:
   - DART 수주·계약 공시 (시장이 아직 모르는 원천 정보)
   - 더일렉·AI타임스 전문 미디어 단독 보도
   - 글로벌 고객사가 52w 신고가인데 한국 공급사는 후행(70~85%) — 갭 추격
3. 이미 3개월 100%+ 오른 종목은 후보에서 배제(선반영). 52w 70~90% 범위가 진짜 기회.
4. Q(수요 증가) 또는 P(가격 상승) 실질 근거 없으면 가설 폐기.

오늘 발견한 패턴 예시 — 한화엔진(082740): DART에서 AI 데이터센터 비상발전기 2000억 계약 + 흑자전환 공시 발견. 주류 언론 미보도. 주가 52w 71.7% 후행. 이런 패턴을 찾아라."""

IDEA_TOOL = {
    "name": "save_macro_idea",
    "description": "도출한 투자 가설을 구조화된 JSON으로 저장",
    "input_schema": {
        "type": "object",
        "required": ["title", "background", "causal_chain", "play_mode", "total_score",
                     "directness", "leverage", "scalability_or_rotation", "technical_alignment",
                     "directness_reason", "leverage_reason", "scalability_or_rotation_reason",
                     "technical_alignment_reason", "market_timing", "critical_risk", "candidates"],
        "properties": {
            "title": {"type": "string"},
            "background": {"type": "string"},
            "causal_chain": {"type": "string"},
            "play_mode": {"type": "string", "enum": ["Global_Re_rating_Play", "Domestic_Alternative_Play"]},
            "total_score": {"type": "integer", "minimum": 0, "maximum": 100},
            "directness": {"type": "integer"},
            "leverage": {"type": "integer"},
            "scalability_or_rotation": {"type": "integer"},
            "technical_alignment": {"type": "integer"},
            "directness_reason": {"type": "string"},
            "leverage_reason": {"type": "string"},
            "scalability_or_rotation_reason": {"type": "string"},
            "technical_alignment_reason": {"type": "string"},
            "market_timing": {"type": "string"},
            "critical_risk": {"type": "string"},
            "candidates": {
                "type": "array",
                "maxItems": 8,
                "items": {
                    "type": "object",
                    "required": ["ticker", "name", "role", "near_52w_high", "ret_1m", "ret_3m",
                                 "early_signal_score", "signal_flag"],
                    "properties": {
                        "ticker": {"type": "string"},
                        "name": {"type": "string"},
                        "role": {"type": "string"},
                        "near_52w_high": {"type": "number"},
                        "ret_1m": {"type": "number"},
                        "ret_3m": {"type": "number"},
                        "early_signal_score": {"type": "number"},
                        "signal_flag": {"type": "string"},
                        "hundredx_match": {"type": ["string", "null"]},
                    },
                },
            },
        },
    },
}


def build_user_prompt(snapshot: dict, price_fetcher) -> str:
    theme_txt = "\n".join(
        f"  Rank{r['rank']}: [{r['theme']}] score={r['score']} aligned={r['aligned']}"
        for r in snapshot["theme_ranks"]
    )
    dart_txt = "\n".join(
        f"  [{f['filed_at'][:10]}] {f['ticker']} | {f['headline']} "
        f"| {f['parsed_amount']}억 → {f.get('parsed_customer','')}"
        for f in snapshot["dart_filings"]
    ) or "  없음"
    bigtech_txt = "\n".join(
        f"  [{b['published_at'][:10]}] {b['title']}" for b in snapshot["bigtech"]
    ) or "  없음"

    # 카테고리별 매크로 뉴스 요약
    cats: dict[str, list] = {}
    for n in snapshot["macro_news"]:
        cats.setdefault(n["category"], []).append(n["title"])
    news_txt = ""
    for cat, titles in sorted(cats.items(), key=lambda x: -len(x[1])):
        news_txt += f"\n  [{cat} {len(titles)}건]\n"
        news_txt += "\n".join(f"    - {t}" for t in titles[:8])

    broker_txt = "\n".join(
        f"  [{b['published_at'][:10]}] {b['ticker']} | {b['title']}"
        for b in snapshot["broker_reports"][:50]
    )

    return f"""오늘 날짜: {date.today().isoformat()}

## Step 0 — 테마 랭킹
{theme_txt}

## Step 1 — 핵심 선행 신호

### DART 수주·계약 공시 (원천 정보 — 최우선 확인)
{dart_txt}

### 빅테크 거물 발언
{bigtech_txt}

### 매크로 뉴스 카테고리별
{news_txt}

### 증권사 리포트 (후행 참고)
{broker_txt}

---

위 데이터를 분석해:
1. DART 공시에서 시장이 아직 모르는 수주·계약을 먼저 확인하라.
2. 테마 랭킹 상위 + 더일렉/Bloomberg 전문 미디어 단독 보도에서 글로벌 선행→한국 후행 갭을 찾아라.
3. Q/P 실질 근거가 있는 하나의 가설을 도출하고, 밸류체인 후보 6~9개를 조기신호스코어로 정렬하라.
4. save_macro_idea 도구를 호출해 결과를 저장하라.

후보 종목의 52w 신고가 근접도는 직접 계산한다:
{price_fetcher.__doc__ or '(price_fetcher 제공됨)'}
"""


def call_claude(user_prompt: str, api_key: str, price_cb) -> dict | None:
    """Claude API로 가설 도출 후 tool_use 결과 반환."""
    ai = anthropic.Anthropic(api_key=api_key)
    messages = [{"role": "user", "content": user_prompt}]

    for attempt in range(3):
        resp = ai.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            tools=[IDEA_TOOL],
            tool_choice={"type": "any"},
            messages=messages,
        )
        # tool_use 블록 추출
        for block in resp.content:
            if block.type == "tool_use" and block.name == "save_macro_idea":
                return block.input
        # tool_use가 없으면 텍스트 응답을 messages에 추가해 재시도
        messages.append({"role": "assistant", "content": resp.content})
        messages.append({"role": "user", "content": "save_macro_idea 도구를 반드시 호출해 결과를 저장해주세요."})

    return None


# ─── 3. Supabase 저장 ─────────────────────────────────────────────────────────

def save_idea(idea: dict, client) -> str | None:
    payload = {
        "date": date.today().isoformat(),
        "title": idea["title"],
        "background": idea["background"],
        "causal_chain": idea["causal_chain"],
        "play_mode": idea["play_mode"],
        "total_score": idea["total_score"],
        "directness": idea["directness"],
        "leverage": idea["leverage"],
        "scalability_or_rotation": idea["scalability_or_rotation"],
        "technical_alignment": idea["technical_alignment"],
        "directness_reason": idea["directness_reason"],
        "leverage_reason": idea["leverage_reason"],
        "scalability_or_rotation_reason": idea["scalability_or_rotation_reason"],
        "technical_alignment_reason": idea["technical_alignment_reason"],
        "market_timing": idea["market_timing"],
        "critical_risk": idea["critical_risk"],
        "candidates": idea["candidates"],
        "raw_json": {k: v for k, v in idea.items() if k != "candidates"},
    }
    res = retry_execute(
        lambda: client.table("macro_ideas").insert(payload).execute()
    )
    rows = res.data or []
    return rows[0]["id"] if rows else None


# ─── 4. 가격 데이터 보강 ─────────────────────────────────────────────────────

def enrich_candidates(candidates: list[dict], supabase_url: str, service_key: str) -> list[dict]:
    """candidates의 near_52w_high/ret_1m/ret_3m/early_signal_score가 비어있으면 실제 가격으로 채운다."""
    enriched = []
    for c in candidates:
        if not c.get("near_52w_high") and c.get("ticker"):
            price_data = fetch_price(c["ticker"], supabase_url, service_key)
            if price_data:
                c = {**c, **price_data}
        enriched.append(c)
    return sorted(enriched, key=lambda x: x.get("early_signal_score", 0), reverse=True)


# ─── 5. 메인 ─────────────────────────────────────────────────────────────────

def run() -> None:
    supabase_url = os.environ["SUPABASE_URL"]
    service_key = os.environ["SUPABASE_SERVICE_KEY"]
    api_key = os.environ["ANTHROPIC_API_KEY"]

    sb = get_client()

    logger.info("Step 1: 데이터 수집 중...")
    snapshot = fetch_news_snapshot(sb)
    logger.info(
        "macro_news=%d, dart=%d, broker=%d, themes=%d",
        len(snapshot["macro_news"]),
        len(snapshot["dart_filings"]),
        len(snapshot["broker_reports"]),
        len(snapshot["theme_ranks"]),
    )

    def price_fetcher(ticker: str) -> dict | None:
        return fetch_price(ticker, supabase_url, service_key)
    price_fetcher.__doc__ = "fetch_price(ticker) → {near_52w_high, ret_1m, ret_3m, early_signal_score, signal_flag}"

    user_prompt = build_user_prompt(snapshot, price_fetcher)

    logger.info("Step 2-4: Claude API로 가설 도출 중...")
    idea = call_claude(user_prompt, api_key, price_fetcher)
    if not idea:
        logger.error("가설 도출 실패 — Claude가 tool_use를 호출하지 않음")
        return

    # 가격 데이터 보강 (Claude가 직접 계산하지 못한 경우 대비)
    idea["candidates"] = enrich_candidates(idea.get("candidates", []), supabase_url, service_key)

    logger.info("Step 5: Supabase 저장 중...")
    idea_id = save_idea(idea, sb)
    if idea_id:
        logger.info("저장 완료: %s | %s (총점 %d)", idea_id, idea["title"][:50], idea["total_score"])
        print(f"\n✅ [{idea['total_score']}점] {idea['title']}")
        print(f"   ID: {idea_id}")
        if idea.get("candidates"):
            print("   Top 후보:")
            for c in idea["candidates"][:3]:
                print(f"     {c['signal_flag']} {c['ticker']}({c['name']}) "
                      f"52w={c.get('near_52w_high','?')}% | {c['role']}")
    else:
        logger.error("저장 실패")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    run()
