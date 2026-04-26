"""Golden signal detector — report 2-D 8선 common structure.

"수주 + 빅네임 + CAPEX" 3종 중 2개 이상 동시 탐지 시 golden=True.
Persists trigger_events to Supabase and marks golden=True when threshold met.
"""
from __future__ import annotations
import logging
from datetime import datetime, timezone

from .classifier import classify_filing, TriggerResult
from ..upsert import get_client

logger = logging.getLogger(__name__)

GOLDEN_TRIGGER_TYPES = {"단일_수주", "CAPEX_증설", "빅테크_파트너", "글로벌_메가계약"}
GOLDEN_THRESHOLD = 2  # need 2+ golden-type triggers simultaneously


def _is_golden_type(t: TriggerResult) -> bool:
    return t.trigger_type in GOLDEN_TRIGGER_TYPES and t.confidence >= 0.4


def detect_golden(filing: dict) -> tuple[bool, list[TriggerResult]]:
    """Classify filing and determine if it is a golden signal.

    Returns (golden: bool, all_triggers: list[TriggerResult])
    """
    results = classify_filing(filing)
    golden_hits = [r for r in results if _is_golden_type(r)]
    golden = len(golden_hits) >= GOLDEN_THRESHOLD
    if golden:
        logger.info(
            "GOLDEN signal: ticker=%s types=%s",
            filing.get("ticker", "?"),
            [r.trigger_type for r in golden_hits],
        )
    return golden, results


def process_filing(filing: dict) -> list[dict]:
    """Classify a filing, persist trigger_events, return inserted rows."""
    client = get_client()
    ticker = filing.get("ticker", "")
    filing_id = filing.get("id")

    golden, results = detect_golden(filing)
    if not results:
        return []

    now = datetime.now(timezone.utc).isoformat()
    rows = []
    for r in results:
        rows.append({
            "ticker": ticker,
            "event_type": r.trigger_type,
            "detected_at": now,
            "confidence": r.confidence,
            "source_filing_id": filing_id,
            "matched_keywords": r.matched_keywords,
            "summary": r.summary,
            "golden": golden,
            "rise_category": r.rise_category,
        })

    try:
        res = client.table("trigger_events").insert(rows).execute()
        inserted = res.data or []
        logger.info("Inserted %d trigger_events for %s", len(inserted), ticker)

        if golden:
            _maybe_add_to_watchlist_candidates(client, ticker, rows)

        return inserted
    except Exception as e:
        logger.warning("trigger_events insert error for %s: %s", ticker, e)
        return []


def _maybe_add_to_watchlist_candidates(client, ticker: str, trigger_rows: list[dict]) -> None:
    """Add ticker as watchlist candidate if not already present."""
    try:
        existing = (
            client.table("watchlist")
            .select("id")
            .eq("ticker", ticker)
            .execute()
        )
        if existing.data:
            return

        client.table("watchlist").insert({
            "ticker": ticker,
            "status": "candidate",
            "notes": f"Golden signal: {', '.join(r['event_type'] for r in trigger_rows[:2])}",
        }).execute()
        logger.info("Added %s to watchlist candidates (golden signal)", ticker)
    except Exception as e:
        logger.warning("Watchlist candidate add error for %s: %s", ticker, e)


def run_for_unprocessed(limit: int = 100) -> int:
    """Process unprocessed filings (no trigger_events yet)."""
    client = get_client()

    # Fetch recent filings that haven't been classified yet
    # We identify these by checking trigger_events for each filing
    # For efficiency, fetch filings from last 7 days
    from datetime import timedelta, date
    cutoff = (date.today() - timedelta(days=7)).isoformat()

    res = (
        client.table("filings")
        .select("id, ticker, headline, raw_text, filed_at")
        .gte("filed_at", cutoff)
        .order("filed_at", desc=True)
        .limit(limit)
        .execute()
    )
    filings = res.data or []

    # Check which ones already have trigger_events
    processed_ids: set[str] = set()
    if filings:
        filing_ids = [str(f["id"]) for f in filings]
        ev_res = (
            client.table("trigger_events")
            .select("source_filing_id")
            .in_("source_filing_id", filing_ids)
            .execute()
        )
        processed_ids = {str(r["source_filing_id"]) for r in (ev_res.data or [])}

    new_filings = [f for f in filings if str(f["id"]) not in processed_ids]
    logger.info("Processing %d unclassified filings", len(new_filings))

    count = 0
    for filing in new_filings:
        inserted = process_filing(filing)
        count += len(inserted)

    return count


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    count = run_for_unprocessed()
    print(f"Processed {count} trigger events")
