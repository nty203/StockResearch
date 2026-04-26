"""Enqueue stocks for agent analysis.

Adds stocks with score >= threshold (from settings) to analysis_queue.
Generates prompt bundle MD and uploads to Supabase Storage.
Token budget: ~2500 tokens total per bundle (configurable via settings).
"""
from __future__ import annotations
import json
import logging
from datetime import date, datetime, timezone
from io import BytesIO

import tiktoken

from ..upsert import get_client, pipeline_run
from ..screening.settings_loader import load_settings

logger = logging.getLogger(__name__)

PROMPT_TYPES = ["demand", "moat", "trigger", "narrative", "risk"]
DEFAULT_SCORE_THRESHOLD = 65
DEFAULT_MAX_TOKENS = 2500

# Token budget per section (must sum to < DEFAULT_MAX_TOKENS)
SECTION_BUDGETS = {
    "financials": 500,
    "filings": 900,   # 3 filings × 300
    "news": 1000,     # 5 news × 200
    "prompt_template": 2000,
}

PROMPT_TEMPLATES = {
    "demand": "수요 분석 프롬프트: 이 기업의 제품/서비스에 대한 수요 구조를 분석하세요. 핵심 고객, TAM, 수요 드라이버를 중심으로.",
    "moat": "해자 분석 프롬프트: 이 기업의 경쟁 우위(해자)를 분석하세요. 기술 장벽, 고객 전환 비용, 네트워크 효과, 규모의 경제를 중심으로.",
    "trigger": "트리거 분석 프롬프트: 향후 12-24개월 내 주가 10배 상승을 촉발할 수 있는 이벤트를 분석하세요. 수주 파이프라인, CAPEX 사이클, 규제 변화를 중심으로.",
    "narrative": "내러티브 분석 프롬프트: 이 기업의 10배 상승 스토리를 한 단락으로 서술하세요. 시장 기회, 실행력, 타이밍을 중심으로.",
    "risk": "리스크 분석 프롬프트: 이 기업의 핵심 리스크 3가지를 분석하세요. 각 리스크의 발생 가능성, 영향도, 완화 방안을 포함하세요.",
}


def _get_encoding() -> tiktoken.Encoding:
    return tiktoken.get_encoding("cl100k_base")


def _count_tokens(text: str) -> int:
    enc = _get_encoding()
    return len(enc.encode(text))


def _truncate_to_budget(text: str, budget: int, label: str) -> str:
    """Truncate text to fit within token budget."""
    enc = _get_encoding()
    tokens = enc.encode(text)
    if len(tokens) <= budget:
        return text
    truncated = enc.decode(tokens[:budget])
    logger.debug("Truncated %s: %d → %d tokens", label, len(tokens), budget)
    return truncated + "\n[truncated]"


def _build_financials_section(client, ticker: str, budget: int) -> str:
    """Build financials summary section."""
    res = (
        client.table("financials_q")
        .select("fq, revenue, op_income, op_margin, roe, roic, fcf, debt_ratio")
        .eq("ticker", ticker)
        .order("fq", desc=True)
        .limit(4)
        .execute()
    )
    fins = res.data or []
    if not fins:
        return "## 재무 데이터\n데이터 없음\n"

    lines = ["## 재무 데이터 (최근 4분기)"]
    for f in fins:
        lines.append(
            f"- {f['fq']}: 매출 {f.get('revenue', 'N/A')} | "
            f"영업이익률 {f.get('op_margin', 'N/A')}% | "
            f"ROIC {f.get('roic', 'N/A')}% | "
            f"FCF {f.get('fcf', 'N/A')}"
        )
    text = "\n".join(lines) + "\n"
    return _truncate_to_budget(text, budget, f"{ticker}/financials")


def _build_filings_section(client, ticker: str, budget: int) -> str:
    """Build recent filings section (up to 3)."""
    from datetime import timedelta
    cutoff = (date.today() - timedelta(days=90)).isoformat()
    res = (
        client.table("filings")
        .select("headline, filed_at, raw_text, keywords")
        .eq("ticker", ticker)
        .gte("filed_at", cutoff)
        .order("filed_at", desc=True)
        .limit(3)
        .execute()
    )
    filings = res.data or []
    if not filings:
        return "## 최근 공시\n공시 없음\n"

    per_filing_budget = budget // max(1, len(filings))
    lines = ["## 최근 공시"]
    for f in filings:
        snippet = (f.get("raw_text") or "")[:200]
        lines.append(
            f"- [{f.get('filed_at', '')[:10]}] {f.get('headline', '')}\n  {snippet}"
        )
    text = "\n".join(lines) + "\n"
    return _truncate_to_budget(text, budget, f"{ticker}/filings")


def _build_news_section(client, ticker: str, budget: int) -> str:
    """Build recent news section (up to 5)."""
    from datetime import timedelta
    cutoff = (date.today() - timedelta(days=30)).isoformat()
    res = (
        client.table("news")
        .select("title, summary, published_at, source")
        .eq("ticker", ticker)
        .gte("published_at", cutoff)
        .order("published_at", desc=True)
        .limit(5)
        .execute()
    )
    news = res.data or []
    if not news:
        return "## 최근 뉴스\n뉴스 없음\n"

    lines = ["## 최근 뉴스"]
    for n in news:
        lines.append(
            f"- [{n.get('published_at', '')[:10]}] {n.get('title', '')} "
            f"({n.get('source', '')})"
        )
        if n.get("summary"):
            lines.append(f"  {n['summary'][:100]}")
    text = "\n".join(lines) + "\n"
    return _truncate_to_budget(text, budget, f"{ticker}/news")


def _build_prompt_bundle(client, ticker: str, prompt_type: str, max_tokens: int) -> str:
    """Build the full prompt bundle MD for a ticker + prompt type."""
    fin_budget = SECTION_BUDGETS["financials"]
    fil_budget = SECTION_BUDGETS["filings"]
    news_budget = SECTION_BUDGETS["news"]
    tmpl_budget = SECTION_BUDGETS["prompt_template"]

    header = f"# 분석 대상: {ticker} | 프롬프트 유형: {prompt_type}\n\n"
    financials = _build_financials_section(client, ticker, fin_budget)
    filings = _build_filings_section(client, ticker, fil_budget)
    news = _build_news_section(client, ticker, news_budget)

    template = PROMPT_TEMPLATES.get(prompt_type, "")
    template_section = f"## 분석 지시\n{template}\n"
    template_section = _truncate_to_budget(template_section, tmpl_budget, f"{ticker}/template")

    bundle = header + financials + "\n" + filings + "\n" + news + "\n" + template_section

    total = _count_tokens(bundle)
    if total > max_tokens:
        logger.warning(
            "Bundle for %s/%s is %d tokens (max %d) — truncating news",
            ticker, prompt_type, total, max_tokens
        )
        # Shrink news section first
        reduced_news_budget = max(100, news_budget - (total - max_tokens))
        news = _build_news_section(client, ticker, reduced_news_budget)
        bundle = header + financials + "\n" + filings + "\n" + news + "\n" + template_section

    return bundle


def enqueue_ticker(client, ticker: str, prompt_type: str, run_date: str, max_tokens: int) -> dict | None:
    """Create one queue item for a ticker + prompt_type."""
    # Check if already queued (PENDING or CLAIMED)
    existing = (
        client.table("analysis_queue")
        .select("id, status")
        .eq("ticker", ticker)
        .eq("prompt_type", prompt_type)
        .in_("status", ["PENDING", "CLAIMED"])
        .execute()
    )
    if existing.data:
        logger.debug("Already queued: %s/%s", ticker, prompt_type)
        return None

    # Build prompt bundle
    bundle_md = _build_prompt_bundle(client, ticker, prompt_type, max_tokens)

    # Upload to Supabase Storage
    storage_path = f"analysis_queue/{ticker}_{prompt_type}_{run_date}.md"
    try:
        client.storage.from_("analysis-prompts").upload(
            path=storage_path,
            file=BytesIO(bundle_md.encode("utf-8")),
            file_options={"content-type": "text/markdown; charset=utf-8", "upsert": "true"},
        )
    except Exception as e:
        logger.warning("Storage upload failed for %s/%s: %s", ticker, prompt_type, e)
        storage_path = None  # still enqueue, just without storage path

    # Insert queue row
    row = {
        "ticker": ticker,
        "prompt_type": prompt_type,
        "status": "PENDING",
        "storage_path_prompt": storage_path,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        res = client.table("analysis_queue").insert(row).execute()
        return (res.data or [None])[0]
    except Exception as e:
        logger.warning("Queue insert error for %s/%s: %s", ticker, prompt_type, e)
        return None


def run(run_date: str | None = None) -> int:
    """Enqueue all eligible stocks for agent analysis."""
    client = get_client()
    settings = load_settings(client)
    threshold = float(settings.get("enqueue_score_threshold", DEFAULT_SCORE_THRESHOLD))
    max_tokens = int(settings.get("max_context_tokens", DEFAULT_MAX_TOKENS))

    if run_date is None:
        run_date = date.today().isoformat()

    # Fetch stocks that passed filters and scored >= threshold
    res = (
        client.table("screen_scores")
        .select("ticker, score_10x, passed")
        .eq("run_date", run_date)
        .eq("passed", True)
        .gte("score_10x", threshold)
        .order("score_10x", desc=True)
        .execute()
    )
    eligible = res.data or []

    # Also include golden signal tickers
    from datetime import timedelta
    golden_cutoff = (date.today() - timedelta(days=7)).isoformat()
    golden_res = (
        client.table("trigger_events")
        .select("ticker")
        .eq("golden", True)
        .gte("detected_at", golden_cutoff)
        .execute()
    )
    golden_tickers = {r["ticker"] for r in (golden_res.data or [])}

    # Merge eligible tickers
    score_tickers = {r["ticker"] for r in eligible}
    all_tickers = score_tickers | golden_tickers
    logger.info(
        "Enqueue candidates: %d by score, %d by golden signal, %d total",
        len(score_tickers), len(golden_tickers), len(all_tickers)
    )

    count = 0
    with pipeline_run(client, "queue") as (rows_out, _):
        for ticker in all_tickers:
            for prompt_type in PROMPT_TYPES:
                item = enqueue_ticker(client, ticker, prompt_type, run_date, max_tokens)
                if item:
                    count += 1
        rows_out[0] = count

    logger.info("Enqueued %d queue items for %s", count, run_date)
    return count


if __name__ == "__main__":
    import argparse
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=None)
    args = parser.parse_args()
    n = run(args.date)
    print(f"Enqueued {n} items")
