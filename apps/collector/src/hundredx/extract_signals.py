"""Step 2: Auto-extract pre-rise signals + auto-categorize.

For each library stock with rise_start_date set but pre_rise_signals empty:
  1. Fetch financials_q in (rise_start_date - 18mo, rise_start_date) window
  2. Fetch filings in same window
  3. Compute quant signals: BCR, OPM transition, revenue growth, backlog YoY
  4. Run all 7 category detectors against this historical data
  5. Pick the detector with HIGHEST confidence as the primary category
  6. Build fingerprint JSONB:
     { quant: {bcr_at_signal, opm_*, ...},
       keywords: [union of matched_keywords from triggered detectors],
       min_keyword_matches: max(1, len(keywords) // 3),
       sector_required: stocks.sector_tag,
       lead_months: 12,
       auto_extracted: true }
  7. UPDATE hundredx_library_stocks SET pre_rise_signals = ..., category = ...

This requires historical financials_q + filings data. For now, the DB only has
recent (2024+) data; older library entries will produce empty signals. A
historical backfill via DART can be added later.

Usage:
  uv run python -m src.hundredx.extract_signals
  uv run python -m src.hundredx.extract_signals --ticker 086520
"""
from __future__ import annotations
import argparse
import logging
from datetime import datetime, timedelta
from typing import Any

from ..upsert import get_client, pipeline_run
from . import keywords as cls

logger = logging.getLogger(__name__)


WINDOW_MONTHS_BEFORE = 18

# Keyword set per category (subset of classifier.py — used to bias category selection
# and produce fingerprint keywords automatically)
CATEGORY_KEYWORD_SETS: dict[str, list[str]] = {
    "수주잔고_선행":   cls.GLOBAL_MEGA_KEYWORDS,
    "빅테크_파트너":   cls.BIGTECH_KEYWORDS + cls.BIGTECH_PARTNER_KEYWORDS,
    "플랫폼_독점":     cls.MONOPOLY_KEYWORDS + cls.TECH_BREAKTHROUGH_KEYWORDS,
    "수익성_급전환":   cls.PROFITABILITY_KEYWORDS,
    "정책_수혜":       cls.GEOPOLITICAL_KEYWORDS + cls.REGULATORY_KEYWORDS,
    "공급_병목":       cls.SUPPLY_BOTTLENECK_KEYWORDS + cls.RAW_MATERIAL_KEYWORDS,
    "임상_파이프라인": cls.BIOTECH_PIPELINE_KEYWORDS,
}


def _fetch_financials_around(client, ticker: str, rise_start: str) -> list[dict]:
    """Fetch financials_q rows within (rise_start - 18mo, rise_start)."""
    # fq is text like '2022Q3' — fetch all rows for ticker, filter in Python.
    res = (
        client.table("financials_q")
        .select("ticker, fq, revenue, op_income, op_margin, roe, roic, fcf, debt_ratio, order_backlog")
        .eq("ticker", ticker)
        .order("fq", desc=True)
        .execute()
    )
    return res.data or []


def _fq_to_date(fq: str) -> datetime | None:
    """'2022Q3' → datetime(2022, 9, 30) (end of quarter)."""
    try:
        year, q = int(fq[:4]), int(fq[-1])
        month = q * 3
        # Approximate end-of-quarter day; fine for window comparison
        return datetime(year, month, 28)
    except (ValueError, IndexError):
        return None


def _fetch_filings_around(client, ticker: str, rise_start: str, months_before: int = WINDOW_MONTHS_BEFORE) -> list[dict]:
    """Fetch filings within (rise_start - months_before, rise_start)."""
    rise_dt = datetime.fromisoformat(rise_start)
    start_dt = rise_dt - timedelta(days=int(months_before * 30.5))
    res = (
        client.table("filings")
        .select("id, ticker, headline, raw_text, filed_at, parsed_amount")
        .eq("ticker", ticker)
        .gte("filed_at", start_dt.isoformat())
        .lt("filed_at", rise_dt.isoformat())
        .order("filed_at", desc=True)
        .limit(2000)
        .execute()
    )
    return res.data or []


def _compute_quant_at_rise(financials: list[dict], rise_start: str) -> dict[str, float]:
    """Compute BCR, OPM transition, revenue growth from financials_q before rise_start."""
    rise_dt = datetime.fromisoformat(rise_start)
    # Filter to quarters BEFORE rise_start, sorted desc (most recent first)
    relevant = []
    for f in financials:
        d = _fq_to_date(f.get("fq", ""))
        if d and d <= rise_dt:
            relevant.append(f)
    if not relevant:
        return {}

    out: dict[str, float] = {}
    latest = relevant[0]
    prev = relevant[1] if len(relevant) > 1 else None

    # BCR
    backlog = latest.get("order_backlog")
    revenue_ttm = sum((r.get("revenue") or 0) for r in relevant[:4]) or None
    if backlog is not None and revenue_ttm and revenue_ttm > 0:
        out["bcr_at_signal"] = round(backlog / revenue_ttm, 3)

    # Backlog YoY
    if backlog is not None and len(relevant) >= 5:
        backlog_prev = relevant[4].get("order_backlog")
        if backlog_prev and backlog_prev > 0:
            out["backlog_yoy_pct"] = round((backlog - backlog_prev) / backlog_prev * 100, 1)

    # OPM transition
    opm_now = latest.get("op_margin")
    opm_prev = prev.get("op_margin") if prev else None
    if opm_now is not None:
        out["opm_at_signal"] = round(opm_now, 2)
    if opm_prev is not None:
        out["opm_prev"] = round(opm_prev, 2)
    if opm_now is not None and opm_prev is not None:
        out["opm_delta_at_signal"] = round(opm_now - opm_prev, 2)

    # Revenue growth (TTM vs previous year TTM)
    if len(relevant) >= 8:
        rev_prev_ttm = sum((r.get("revenue") or 0) for r in relevant[4:8])
        if revenue_ttm and rev_prev_ttm and rev_prev_ttm > 0:
            out["revenue_growth_yoy"] = round((revenue_ttm - rev_prev_ttm) / rev_prev_ttm * 100, 1)

    return out


def _categorize_from_filings(filings: list[dict]) -> tuple[str, list[str], int]:
    """Score each category by total keyword hits across all filings.

    Returns: (best_category, matched_keywords_for_best, hit_count)
    """
    if not filings:
        return "미분류", [], 0

    # Combine all filing text
    combined = " ".join(
        ((f.get("raw_text") or "") + " " + (f.get("headline") or "")).lower()
        for f in filings
    )

    category_scores: dict[str, tuple[int, list[str]]] = {}
    for cat, keywords in CATEGORY_KEYWORD_SETS.items():
        matched = [kw for kw in keywords if kw.lower() in combined]
        category_scores[cat] = (len(matched), matched)

    best_cat = max(category_scores.items(), key=lambda x: x[1][0])
    cat_name, (hit_count, matched_kws) = best_cat
    if hit_count == 0:
        return "미분류", [], 0
    return cat_name, matched_kws, hit_count


def _max_filing_amount(filings: list[dict]) -> float | None:
    """Largest parsed_amount across the window's filings (in 억 KRW units)."""
    amounts = [f.get("parsed_amount") for f in filings if f.get("parsed_amount") is not None]
    return max(amounts) if amounts else None


def extract_for_entry(client, lib_row: dict, force: bool = False) -> dict | None:
    """Extract signals for one library entry. Returns updated row or None if skipped."""
    ticker = lib_row["ticker"]
    rise_start = lib_row.get("rise_start_date")
    if not rise_start:
        return None

    # Skip if already has pre_rise_signals (unless --force)
    existing_signals = lib_row.get("pre_rise_signals")
    if existing_signals and not force:
        return None

    # Fetch sector_tag
    sector_res = (
        client.table("stocks").select("sector_tag, market").eq("ticker", ticker).single().execute()
    )
    sector_tag = (sector_res.data or {}).get("sector_tag") if sector_res.data else None

    financials = _fetch_financials_around(client, ticker, rise_start)
    filings = _fetch_filings_around(client, ticker, rise_start)

    quant = _compute_quant_at_rise(financials, rise_start)
    category, keywords, kw_hits = _categorize_from_filings(filings)
    amount_threshold = _max_filing_amount(filings)

    fingerprint: dict[str, Any] = {
        "auto_extracted": True,
        "extracted_at": datetime.utcnow().isoformat(),
        "data_quality": {
            "financials_count": len(financials),
            "filings_count": len(filings),
            "had_quant": bool(quant),
            "had_keywords": kw_hits > 0,
        },
    }
    if quant:
        fingerprint["quant"] = quant
    if keywords:
        # Dedupe and cap at top 12 keywords for fingerprint
        unique = list(dict.fromkeys(keywords))[:12]
        fingerprint["keywords"] = unique
        fingerprint["min_keyword_matches"] = max(1, len(unique) // 3)
    if sector_tag:
        fingerprint["sector_required"] = sector_tag
    if amount_threshold:
        fingerprint["amount_threshold_billions"] = round(amount_threshold, 1)

    update_payload: dict[str, Any] = {"pre_rise_signals": fingerprint}
    # Update category only if currently 미분류 / NULL and we found one
    if (lib_row.get("category") in (None, "미분류")) and category != "미분류":
        update_payload["category"] = category

    try:
        client.table("hundredx_library_stocks").update(update_payload).eq("id", lib_row["id"]).execute()
        return {"ticker": ticker, "category": update_payload.get("category", lib_row.get("category")),
                "fingerprint": fingerprint}
    except Exception as e:
        logger.warning("Update failed for %s: %s", ticker, e)
        return None


def run(ticker_filter: str | None = None, force: bool = False) -> int:
    client = get_client()
    with pipeline_run(client, "hundredx") as (rows_out, _):
        q = client.table("hundredx_library_stocks").select("*")
        if ticker_filter:
            q = q.eq("ticker", ticker_filter)
        rows = q.execute().data or []
        logger.info("Processing %d library entries", len(rows))

        updated = 0
        for row in rows:
            result = extract_for_entry(client, row, force=force)
            if result:
                updated += 1
                logger.info("Extracted %s -> category=%s, keywords=%d, quant=%d",
                            result["ticker"], result["category"],
                            len(result["fingerprint"].get("keywords", [])),
                            len(result["fingerprint"].get("quant", {})))

        rows_out[0] = updated
        return updated


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser()
    parser.add_argument("--ticker", help="Process only this ticker")
    parser.add_argument("--force", action="store_true", help="Re-extract even if pre_rise_signals exists")
    args = parser.parse_args()
    n = run(ticker_filter=args.ticker, force=args.force)
    print(f"Done: {n} library entries updated")
