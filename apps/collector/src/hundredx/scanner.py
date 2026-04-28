"""100x Category Scanner — runs all 7 detectors across active KR stocks.

Lifecycle per daily run:
  1. Pre-fetch library (12 rows, one query)
  2. Fetch existing first_detected_at values (one bulk query)
  3. Batch-fetch financials + filings (50 tickers at a time)
  4. Run all 7 detectors per stock (skip-and-continue on error)
  5. Upsert results (Python-managed first_detected_at)
  6. Mark exits (exited_at = now() for disappeared categories)
  7. Send Telegram alerts for new entries (alert_sent_at dedup)
"""
from __future__ import annotations
import logging
import os
from datetime import datetime, timezone
from ..upsert import get_client, pipeline_run
from ..utils.db_fetch import bulk_fetch_financials
from .models import CategoryMatch
from .categories.backlog_lead import detect as detect_backlog_lead
from .categories.profit_inflect import detect as detect_profit_inflect
from .categories.bigtech_partner import detect as detect_bigtech_partner
from .categories.platform_mono import detect as detect_platform_mono
from .categories.policy_benefit import detect as detect_policy_benefit
from .categories.supply_choke import detect as detect_supply_choke
from .categories.clinical_pipe import detect as detect_clinical_pipe

logger = logging.getLogger(__name__)

BATCH_SIZE = 50
MIN_CONFIDENCE = float(os.environ.get("HUNDREDX_MIN_CONFIDENCE", "0.5"))

DETECTORS = [
    ("수주잔고_선행",  detect_backlog_lead),
    ("수익성_급전환",  detect_profit_inflect),
    ("빅테크_파트너",  detect_bigtech_partner),
    ("플랫폼_독점",    detect_platform_mono),
    ("정책_수혜",      detect_policy_benefit),
    ("공급_병목",      detect_supply_choke),
    ("임상_파이프라인", detect_clinical_pipe),
]


# ── Library pre-fetch ──────────────────────────────────────────────────────────

def _load_library(client) -> dict[str, list[dict]]:
    """Fetch all library stocks in one query, group by category."""
    rows = client.table("hundredx_library_stocks").select("*").execute().data or []
    lib: dict[str, list[dict]] = {}
    for r in rows:
        lib.setdefault(r["category"], []).append(r)
    return lib


def _find_analog_financial(lib: dict, category: str, signal_key: str, current_val: float) -> dict | None:
    """For financial detectors: closest library stock by numeric signal value."""
    rows = lib.get(category, [])
    candidates = [
        r for r in rows
        if (r.get("pre_rise_signals") or {}).get(signal_key) is not None
    ]
    if not candidates:
        return None
    return min(
        candidates,
        key=lambda r: abs(float(r["pre_rise_signals"][signal_key]) - current_val),
    )


def _find_analog_text(lib: dict, category: str) -> dict | None:
    """For text detectors: most recent library stock in same category."""
    rows = lib.get(category, [])
    if not rows:
        return None
    return max(rows, key=lambda r: r.get("rise_start_date") or "")


# ── Existing state fetch ──────────────────────────────────────────────────────

def _fetch_existing(client, tickers: list[str]) -> dict[tuple[str, str], dict]:
    """Bulk-fetch existing hundredx_category_matches for given tickers.

    Returns dict keyed by (ticker, category) with the existing row.
    """
    if not tickers:
        return {}
    res = (
        client.table("hundredx_category_matches")
        .select("ticker, category, first_detected_at, exited_at, alert_sent_at")
        .in_("ticker", tickers)
        .execute()
    )
    return {(r["ticker"], r["category"]): r for r in (res.data or [])}


# ── Filings batch fetch ───────────────────────────────────────────────────────

def _fetch_filings_90d(client, tickers: list[str]) -> dict[str, list[dict]]:
    """Bulk-fetch filings from last 90 days for a batch of tickers."""
    from datetime import timedelta, date
    cutoff = (date.today() - timedelta(days=90)).isoformat()
    res = (
        client.table("filings")
        .select("id, ticker, headline, raw_text, filed_at")
        .in_("ticker", tickers)
        .gte("filed_at", cutoff)
        .order("filed_at", desc=True)
        .limit(10_000)
        .execute()
    )
    result: dict[str, list[dict]] = {}
    for row in (res.data or []):
        result.setdefault(row["ticker"], []).append(row)
    return result


def _fetch_filings_2y(client, tickers: list[str]) -> dict[str, list[dict]]:
    """Bulk-fetch last 2 filings per ticker for clinical_pipe (2-year window)."""
    from datetime import timedelta, date
    cutoff = (date.today() - timedelta(days=730)).isoformat()
    res = (
        client.table("filings")
        .select("id, ticker, headline, raw_text, filed_at")
        .in_("ticker", tickers)
        .gte("filed_at", cutoff)
        .order("filed_at", desc=True)
        .limit(10_000)
        .execute()
    )
    result: dict[str, list[dict]] = {}
    for row in (res.data or []):
        ticker_filings = result.setdefault(row["ticker"], [])
        if len(ticker_filings) < 2:
            ticker_filings.append(row)
    return result


# ── Upsert helpers ────────────────────────────────────────────────────────────

def _resolve_first_detected(
    match: CategoryMatch,
    existing: dict[tuple[str, str], dict],
    now: datetime,
) -> datetime:
    """Determine first_detected_at for this match.

    Rules:
    - New entry (not in existing): now
    - Re-entry after exit (exited_at was set): now (NEW badge fires again)
    - Unchanged active entry: preserve existing first_detected_at
    """
    key = (match.ticker, match.category)
    row = existing.get(key)
    if row is None:
        return now
    if row.get("exited_at") is not None:
        return now  # re-entry: reset
    existing_ts = row.get("first_detected_at")
    if existing_ts:
        try:
            return datetime.fromisoformat(existing_ts.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            pass
    return now


def _upsert_matches(client, matches: list[CategoryMatch], existing: dict, now: datetime) -> None:
    """Upsert all matches to hundredx_category_matches."""
    if not matches:
        return
    rows = []
    for m in matches:
        fda = _resolve_first_detected(m, existing, now)
        rows.append({
            "ticker": m.ticker,
            "category": m.category,
            "confidence": round(m.confidence, 3),
            "evidence": m.evidence,
            "first_detected_at": fda.isoformat(),
            "detected_at": now.isoformat(),
            "exited_at": None,  # clear any prior exit on re-entry
            "analog_ticker": None,   # populated by scanner after analog lookup
            "analog_date": None,
            "analog_multiplier": None,
        })
    try:
        client.table("hundredx_category_matches").upsert(
            rows, on_conflict="ticker,category"
        ).execute()
    except Exception as e:
        logger.warning("upsert_matches error: %s", e)


def _upsert_matches_with_analogs(
    client,
    matches: list[CategoryMatch],
    existing: dict,
    lib: dict,
    now: datetime,
) -> None:
    """Upsert matches with analog fields populated."""
    if not matches:
        return
    rows = []
    for m in matches:
        fda = _resolve_first_detected(m, existing, now)
        analog = _get_analog(lib, m)
        rows.append({
            "ticker": m.ticker,
            "category": m.category,
            "confidence": round(m.confidence, 3),
            "evidence": m.evidence,
            "first_detected_at": fda.isoformat(),
            "detected_at": now.isoformat(),
            "exited_at": None,
            "analog_ticker": analog.get("ticker") if analog else None,
            "analog_date": analog.get("rise_start_date") if analog else None,
            "analog_multiplier": analog.get("peak_multiplier") if analog else None,
        })
    try:
        client.table("hundredx_category_matches").upsert(
            rows, on_conflict="ticker,category"
        ).execute()
    except Exception as e:
        logger.warning("upsert_matches error: %s", e)


def _get_analog(lib: dict, match: CategoryMatch) -> dict | None:
    """Return best analog library stock for this match."""
    category = match.category
    # Financial detectors: use quantitative similarity
    if category == "수주잔고_선행":
        bcr = next((e.get("amount") for e in match.evidence if e.get("source_type") == "bcr"), None)
        if bcr is not None:
            return _find_analog_financial(lib, category, "bcr_at_signal", bcr)
    elif category == "수익성_급전환":
        opm_delta = next((e.get("amount") for e in match.evidence if e.get("source_type") == "opm_delta"), None)
        if opm_delta is not None:
            return _find_analog_financial(lib, category, "opm_delta_at_signal", opm_delta)
    # Text detectors + fallback: most recent in same category
    return _find_analog_text(lib, category)


# ── Exit marking ──────────────────────────────────────────────────────────────

def _mark_exits(client, active_before: set[tuple[str, str]], active_after: set[tuple[str, str]], now: datetime) -> int:
    """Set exited_at for (ticker, category) pairs that disappeared this scan."""
    exited = active_before - active_after
    if not exited:
        return 0
    count = 0
    for ticker, category in exited:
        try:
            client.table("hundredx_category_matches").update(
                {"exited_at": now.isoformat()}
            ).eq("ticker", ticker).eq("category", category).execute()
            count += 1
        except Exception as e:
            logger.warning("exit mark error %s/%s: %s", ticker, category, e)
    return count


# ── Telegram alerts ───────────────────────────────────────────────────────────

def _send_alerts(client, new_matches: list[tuple[str, str, float, str | None]]) -> None:
    """Send Telegram alerts for new category entries (deduped by alert_sent_at).

    new_matches: list of (ticker, category, confidence, analog_summary)
    """
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not bot_token or not chat_id:
        logger.info("Telegram not configured — skipping alerts")
        return

    import urllib.request
    import json
    now = datetime.now(timezone.utc).isoformat()

    if len(new_matches) <= 3:
        for ticker, category, confidence, analog in new_matches:
            msg = f"[100x 시그널] NEW: {ticker}\n카테고리: {category} (신뢰도: {confidence:.2f})"
            if analog:
                msg += f"\n유사 종목: {analog}"
            _telegram_send(bot_token, chat_id, msg)
    else:
        lines = "\n".join(
            f"{i+1}. {t} — {cat} ({conf:.2f}) [NEW]"
            for i, (t, cat, conf, _) in enumerate(new_matches[:3])
        )
        extra = len(new_matches) - 3
        msg = f"[100x 시그널] 오늘 {len(new_matches)}개 종목 신규 탐지\n{lines}"
        if extra > 0:
            msg += f"\n+{extra}개 더 → 앱에서 확인"
        _telegram_send(bot_token, chat_id, msg)

    # Mark alert_sent_at
    for ticker, category, _, _ in new_matches:
        try:
            client.table("hundredx_category_matches").update(
                {"alert_sent_at": now}
            ).eq("ticker", ticker).eq("category", category).execute()
        except Exception as e:
            logger.warning("alert_sent_at update error %s/%s: %s", ticker, category, e)


def _telegram_send(bot_token: str, chat_id: str, text: str) -> None:
    import urllib.request
    import json
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = json.dumps({"chat_id": chat_id, "text": text}).encode()
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    try:
        urllib.request.urlopen(req, timeout=10)
    except Exception as e:
        logger.warning("Telegram send failed: %s", e)


# ── Main scan ─────────────────────────────────────────────────────────────────

def run(min_confidence: float = MIN_CONFIDENCE) -> int:
    """Run all 7 detectors across all active KR stocks. Returns total matches upserted."""
    client = get_client()
    now = datetime.now(timezone.utc)

    with pipeline_run(client, "hundredx") as (rows_out, _):
        # Pre-fetch library (one query, ~12 rows)
        lib = _load_library(client)
        logger.info("Library loaded: %d categories, %d stocks",
                    len(lib), sum(len(v) for v in lib.values()))

        # Fetch active KR stocks
        stocks_res = (
            client.table("stocks")
            .select("ticker, market, sector_tag")
            .eq("is_active", True)
            .in_("market", ["KOSPI", "KOSDAQ"])
            .execute()
        )
        stocks = stocks_res.data or []
        tickers = [s["ticker"] for s in stocks]
        sector_by_ticker = {s["ticker"]: s.get("sector_tag") for s in stocks}
        logger.info("Scanning %d active KR stocks", len(tickers))

        # Pre-fetch all existing matches (for first_detected_at management)
        existing = _fetch_existing(client, tickers)
        active_before: set[tuple[str, str]] = {
            (r["ticker"], r["category"])
            for r in (existing.values())
            if r.get("exited_at") is None
        }

        all_matches: list[CategoryMatch] = []
        active_after: set[tuple[str, str]] = set()

        # Process in batches of 50
        for i in range(0, len(tickers), BATCH_SIZE):
            batch_tickers = tickers[i : i + BATCH_SIZE]
            logger.info("Batch %d/%d (%d tickers)", i // BATCH_SIZE + 1,
                        (len(tickers) + BATCH_SIZE - 1) // BATCH_SIZE, len(batch_tickers))

            # Bulk-fetch financial data
            fin_data = bulk_fetch_financials(client, batch_tickers)

            # Bulk-fetch filings (90d for most detectors, 2y for clinical)
            filings_90d = _fetch_filings_90d(client, batch_tickers)
            filings_2y = _fetch_filings_2y(client, batch_tickers)

            for ticker in batch_tickers:
                stock_data = fin_data.get(ticker, {"ticker": ticker})
                stock_data["ticker"] = ticker
                stock_data["sector_tag"] = sector_by_ticker.get(ticker)
                filings = filings_90d.get(ticker, [])
                filings_clinical = filings_2y.get(ticker, [])

                for category, detector_fn in DETECTORS:
                    try:
                        # clinical_pipe gets 2-year filings; others get 90d
                        f = filings_clinical if category == "임상_파이프라인" else filings
                        result = detector_fn(stock_data, f)
                        if result is not None and result.confidence >= min_confidence:
                            result.ticker = ticker
                            result.category = category
                            all_matches.append(result)
                            active_after.add((ticker, category))
                    except Exception as e:
                        logger.warning("Detector %s error on %s: %s", category, ticker, e)

        # Upsert all matches
        if all_matches:
            _upsert_matches_with_analogs(client, all_matches, existing, lib, now)
            logger.info("Upserted %d category matches", len(all_matches))

        # Mark exits
        exits = _mark_exits(client, active_before, active_after, now)
        if exits:
            logger.info("Marked %d exits", exits)

        # Send alerts for new entries (not yet alerted)
        new_entries: list[tuple[str, str, float, str | None]] = []
        for m in all_matches:
            key = (m.ticker, m.category)
            existing_row = existing.get(key)
            already_alerted = existing_row and existing_row.get("alert_sent_at")
            is_new = existing_row is None or existing_row.get("exited_at") is not None
            if is_new and not already_alerted:
                analog = _get_analog(lib, m)
                analog_summary = None
                if analog:
                    analog_summary = (
                        f"{analog['ticker']} {analog.get('rise_start_date', '')[:7]} "
                        f"→ {analog.get('peak_multiplier', '?')}배"
                    )
                new_entries.append((m.ticker, m.category, m.confidence, analog_summary))

        if new_entries:
            _send_alerts(client, new_entries)
            logger.info("Sent alerts for %d new entries", len(new_entries))

        rows_out[0] = len(all_matches)

    return len(all_matches)


if __name__ == "__main__":
    import argparse
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser()
    parser.add_argument("--min-confidence", type=float, default=MIN_CONFIDENCE)
    args = parser.parse_args()
    total = run(args.min_confidence)
    print(f"Done: {total} category matches")
