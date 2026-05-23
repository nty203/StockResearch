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
from .fingerprint_match import best_match_in_category, FingerprintMatch
from .timeline_match import best_timeline_in_category, progress_to_dict
from .categories.backlog_lead import detect as detect_backlog_lead
from .categories.profit_inflect import detect as detect_profit_inflect
from .categories.bigtech_partner import detect as detect_bigtech_partner
from .categories.platform_mono import detect as detect_platform_mono
from .categories.policy_benefit import detect as detect_policy_benefit
from .categories.supply_choke import detect as detect_supply_choke
from .categories.clinical_pipe import detect as detect_clinical_pipe
from .pptr_detector import BLOCKED_PPTR_CATEGORIES, detect_from_pptr
from .pptr_near_miss import analyze_pptr_near_misses
from .price_performance import PricePerformance, fetch_window_performance
from ..utils import telegram as tg

logger = logging.getLogger(__name__)

BATCH_SIZE = 50
MIN_CONFIDENCE = float(os.environ.get("HUNDREDX_MIN_CONFIDENCE", "0.7"))
PRICE_PERFORMANCE_YEARS = int(os.environ.get("HUNDREDX_PRICE_PERFORMANCE_YEARS", "3"))

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


def _flatten_lib(lib: dict[str, list[dict]]) -> list[dict]:
    """Flatten {category: [rows]} → flat list[row] for fingerprint matcher."""
    out: list[dict] = []
    for rows in lib.values():
        out.extend(rows)
    return out


def _extract_pptr_rules(lib: dict[str, list[dict]]) -> list[dict]:
    """Extract detector_rules from PPTR resolutions across all library stocks."""
    rules = []
    for cat_rows in lib.values():
        for r in cat_rows:
            pptr = r.get("pptr_analysis")
            if pptr and isinstance(pptr, dict) and "resolutions" in pptr:
                for res in pptr["resolutions"]:
                    if "detector_rule" in res:
                        category = res["detector_rule"].get("category", r.get("category"))
                        if category in BLOCKED_PPTR_CATEGORIES:
                            continue
                        producer_id = res.get("producer_id")
                        rules.append({
                            "library_ticker": r["ticker"],
                            "producer_id": producer_id,
                            "rule_id": res.get("rule_id") or f"{r['ticker']}:{producer_id}:{category}",
                            "category": category,
                            "conditions": res["detector_rule"].get("conditions", {}),
                            "performance": res.get("performance") or res.get("performance_summary"),
                        })
    return rules


def _upsert_pptr_rules(client, rules: list[dict]) -> None:
    """Persist PPTR rule definitions so match outcomes can be tracked later."""
    if not rules:
        return
    rows = []
    for rule in rules:
        rows.append({
            "rule_id": rule.get("rule_id"),
            "library_ticker": rule.get("library_ticker"),
            "producer_id": rule.get("producer_id"),
            "category": rule.get("category"),
            "conditions": rule.get("conditions") or {},
            "detector_rule": {
                "category": rule.get("category"),
                "conditions": rule.get("conditions") or {},
            },
            "performance_summary": rule.get("performance") or {},
        })
    try:
        client.table("pptr_rules").upsert(rows, on_conflict="rule_id").execute()
    except Exception as e:
        logger.warning("upsert_pptr_rules error: %s", e)


def _insert_pptr_near_misses(client, near_misses: list[dict], now: datetime) -> None:
    """Persist partial PPTR firings as learning data; never block scanner."""
    if not near_misses:
        return
    rows = []
    seen = set()
    for near in near_misses:
        key = (near.get("rule_id"), near.get("ticker"))
        if key in seen:
            continue
        seen.add(key)
        rows.append({
            "rule_id": near.get("rule_id"),
            "ticker": near.get("ticker"),
            "category": near.get("category"),
            "detected_at": now.isoformat(),
            "near_miss_score": near.get("near_miss_score"),
            "matched_conditions": near.get("matched_conditions") or [],
            "missing_conditions": near.get("missing_conditions") or [],
            "details": near.get("details") or {},
        })
    if not rows:
        return
    try:
        client.table("pptr_rule_near_misses").insert(rows).execute()
    except Exception as e:
        logger.warning("insert_pptr_near_misses error: %s", e)


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

    쪼개기 조회(Chunking)를 적용해 URL 길이 제한 및 400 Bad Request 에러 방지.
    """
    if not tickers:
        return {}

    chunk_size = 500
    rows = []
    for i in range(0, len(tickers), chunk_size):
        chunk = tickers[i : i + chunk_size]
        try:
            res = (
                client.table("hundredx_category_matches")
                .select(
                    "ticker, category, first_detected_at, exited_at, alert_sent_at, "
                    "price_baseline_date, price_baseline_close, price_latest_date, "
                    "price_latest_close, price_peak_date, price_peak_close, "
                    "price_current_multiplier, price_change_pct, "
                    "price_peak_multiplier, price_peak_change_pct, "
                    "price_performance_updated_at"
                )
                .in_("ticker", chunk)
                .execute()
            )
            if res.data:
                rows.extend(res.data)
        except Exception as e:
            logger.warning("Error fetching existing matches chunk: %s", e)

    return {(r["ticker"], r["category"]): r for r in rows}

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

def _signal_date_from_evidence(match: CategoryMatch, now: datetime) -> datetime:
    """evidence에서 실제 시그널 발생일 추출 (공시/뉴스 날짜).

    오늘 탐지했더라도 공시가 2주 전에 났으면 그 날짜를 시그널 날짜로 사용.
    """
    evid = match.evidence or []
    dates: list[str] = []
    for e in evid:
        if not isinstance(e, dict):
            continue
        d = e.get("date") or e.get("filed_at")
        if d:
            try:
                dt = str(d)[:10]
                if dt >= "2020-01-01":
                    dates.append(dt)
            except Exception:
                pass
    if dates:
        earliest = min(dates)
        try:
            return datetime.fromisoformat(earliest + "T00:00:00+00:00")
        except Exception:
            pass
    return now


def _resolve_first_detected(
    match: CategoryMatch,
    existing: dict[tuple[str, str], dict],
    now: datetime,
) -> datetime:
    """Determine first_detected_at for this match.

    Rules:
    - New entry or re-entry: 실제 시그널 발생일 (evidence 공시 날짜, 없으면 now)
    - Unchanged active entry: preserve existing first_detected_at
    """
    key = (match.ticker, match.category)
    row = existing.get(key)
    if row is None or row.get("exited_at") is not None:
        # 신규 탐지 or 재진입: 실제 시그널 발생일로 소급
        return _signal_date_from_evidence(match, now)
    existing_ts = row.get("first_detected_at")
    if existing_ts:
        try:
            return datetime.fromisoformat(existing_ts.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            pass
    return _signal_date_from_evidence(match, now)


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


def _fetch_price_performances(
    matches: list[CategoryMatch],
    market_by_ticker: dict[str, str | None],
) -> dict[str, PricePerformance]:
    """Fetch 3-year low-to-latest performance only for matched tickers."""
    result: dict[str, PricePerformance] = {}
    for ticker in sorted({m.ticker for m in matches}):
        perf = fetch_window_performance(
            ticker,
            market=market_by_ticker.get(ticker),
            years=PRICE_PERFORMANCE_YEARS,
        )
        if perf is not None:
            result[ticker] = perf
    return result


def _price_performance_payload(
    perf: PricePerformance | None,
    existing_row: dict | None,
    now: datetime,
) -> dict:
    """Build DB fields, preserving prior values if a fresh fetch is unavailable."""
    if perf is not None:
        return {
            "price_baseline_date": perf.baseline_date,
            "price_baseline_close": perf.baseline_close,
            "price_latest_date": perf.latest_date,
            "price_latest_close": perf.latest_close,
            "price_peak_date": perf.peak_date,
            "price_peak_close": perf.peak_close,
            "price_current_multiplier": perf.current_multiplier,
            "price_change_pct": perf.current_return_pct,
            "price_peak_multiplier": perf.peak_multiplier,
            "price_peak_change_pct": perf.peak_return_pct,
            "price_performance_updated_at": now.isoformat(),
        }

    existing_row = existing_row or {}
    return {
        "price_baseline_date": existing_row.get("price_baseline_date"),
        "price_baseline_close": existing_row.get("price_baseline_close"),
        "price_latest_date": existing_row.get("price_latest_date"),
        "price_latest_close": existing_row.get("price_latest_close"),
        "price_peak_date": existing_row.get("price_peak_date"),
        "price_peak_close": existing_row.get("price_peak_close"),
        "price_current_multiplier": existing_row.get("price_current_multiplier"),
        "price_change_pct": existing_row.get("price_change_pct"),
        "price_peak_multiplier": existing_row.get("price_peak_multiplier"),
        "price_peak_change_pct": existing_row.get("price_peak_change_pct"),
        "price_performance_updated_at": existing_row.get("price_performance_updated_at"),
    }


def _upsert_matches_with_analogs(
    client,
    matches: list[CategoryMatch],
    existing: dict,
    lib: dict,
    now: datetime,
    price_performances: dict[str, PricePerformance] | None = None,
) -> None:
    """Upsert matches with analog + fingerprint fields populated.

    analog_ticker is derived from the BEST fingerprint match if available
    (more meaningful than 'closest BCR'); falls back to most-recent-in-category.
    """
    if not matches:
        return
    rows = []
    pptr_rows = []
    price_performances = price_performances or {}
    for m in matches:
        fda = _resolve_first_detected(m, existing, now)
        existing_row = existing.get((m.ticker, m.category))
        pptr_match = getattr(m, "pptr_match", None)
        pptr_rule_id = pptr_match.get("rule_id") if pptr_match else None
        pptr_breakdown = pptr_match.get("confidence_breakdown") if pptr_match else None

        # Resolve analog from fingerprint match if present, else fallback
        if m.fingerprint_library_ticker:
            analog = _find_lib_entry(lib, m.fingerprint_library_ticker, m.category)
        else:
            analog = _get_analog(lib, m)

        perf = price_performances.get(m.ticker)
        row = {
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
            "fingerprint_score": (
                round(m.fingerprint_score, 3) if m.fingerprint_score is not None else None
            ),
            "fingerprint_dims": m.fingerprint_dims,
            "timeline_progress": m.timeline_progress,
            "pptr_match": getattr(m, "pptr_match", None),
            "pptr_rule_id": pptr_rule_id,
            "pptr_confidence_breakdown": pptr_breakdown,
        }
        row.update(_price_performance_payload(perf, existing_row, now))
        rows.append(row)
        if pptr_rule_id:
            pptr_rows.append({
                "rule_id": pptr_rule_id,
                "ticker": m.ticker,
                "category": m.category,
                "matched_at": now.isoformat(),
                "confidence": round(m.confidence, 3),
                "confidence_breakdown": pptr_breakdown or {},
                "matched_conditions": pptr_match.get("matched_conditions", []),
                "evidence": m.evidence,
                "as_of_close": perf.latest_close if perf is not None else None,
            })
    try:
        client.table("hundredx_category_matches").upsert(
            rows, on_conflict="ticker,category"
        ).execute()
    except Exception as e:
        logger.warning("upsert_matches error: %s", e)
    if pptr_rows:
        try:
            client.table("pptr_rule_matches").insert(pptr_rows).execute()
        except Exception as e:
            logger.warning("insert_pptr_rule_matches error: %s", e)


def _find_lib_entry(lib: dict, ticker: str, category: str) -> dict | None:
    for row in lib.get(category, []):
        if row.get("ticker") == ticker:
            return row
    return None


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


# ── Category deduplication ───────────────────────────────────────────────────

# Categories that should NEVER be crowded out by other categories
# (they represent fundamentally different investment theses)
# ⚠️  임상_파이프라인은 _ALWAYS_KEEP에서 제거:
#     clinical_pipe.py에 비바이오 섹터 early-exit가 추가됐으므로, 비바이오 종목에서
#     임상이 탐지됐다면 detector 버그 → dedup으로 제거되어야 함.
#     (바이오 종목에서도 임상이 최고 confidence면 to_dedup 1위를 차지하므로 보존됨)
_ALWAYS_KEEP_CATEGORIES = frozenset({
    "수익성_급전환",     # financial event — distinct from supply/partnership
})

# Category priority order for tiebreaking (higher index = higher priority)
_CATEGORY_PRIORITY = {
    "수주잔고_선행":  1,
    "정책_수혜":     2,
    "공급_병목":     3,
    "플랫폼_독점":   4,
    "수익성_급전환": 5,
    "임상_파이프라인": 6,
    "빅테크_파트너": 7,
}


def _deduplicate_categories(matches: list[CategoryMatch]) -> list[CategoryMatch]:
    """Keep only the best-confidence category match per ticker.

    Rationale:
    - Same ticker appearing in 5-7 categories simultaneously creates noise
      and degrades the signal (e.g., 373220 at 0.750 in ALL categories)
    - Exception: categories in _ALWAYS_KEEP_CATEGORIES are preserved alongside
      the best other category (they represent distinct investment theses)

    Algorithm:
    1. For each ticker, identify all matching categories
    2. If ≤1 category → keep as-is
    3. If >1 category:
       a. Among non-always-keep categories, keep only the best (by confidence,
          then by _CATEGORY_PRIORITY)
       b. Always keep _ALWAYS_KEEP_CATEGORIES entries if they also passed threshold
    """
    if not matches:
        return matches

    # Group by ticker
    by_ticker: dict[str, list[CategoryMatch]] = {}
    for m in matches:
        by_ticker.setdefault(m.ticker, []).append(m)

    result: list[CategoryMatch] = []
    dedup_count = 0

    for ticker, ticker_matches in by_ticker.items():
        if len(ticker_matches) <= 1:
            result.extend(ticker_matches)
            continue

        # Split into "always keep" vs "deduplicate"
        always_keep = [m for m in ticker_matches if m.category in _ALWAYS_KEEP_CATEGORIES]
        to_dedup = [m for m in ticker_matches if m.category not in _ALWAYS_KEEP_CATEGORIES]

        kept = list(always_keep)

        if to_dedup:
            # Sort by confidence desc, then category priority desc
            to_dedup.sort(
                key=lambda m: (
                    m.confidence,
                    _CATEGORY_PRIORITY.get(m.category, 0),
                ),
                reverse=True,
            )
            kept.append(to_dedup[0])  # keep best
            demoted = len(to_dedup) - 1
            if demoted > 0:
                dedup_count += demoted
                logger.debug(
                    "Dedup %s: kept %s (conf=%.3f), demoted %d others: %s",
                    ticker,
                    to_dedup[0].category,
                    to_dedup[0].confidence,
                    demoted,
                    [m.category for m in to_dedup[1:]],
                )

        result.extend(kept)

    if dedup_count > 0:
        logger.info(
            "Category dedup: %d matches -> %d (removed %d duplicate categories)",
            len(matches), len(result), dedup_count,
        )

    return result


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
            ).eq("ticker", ticker).eq("category", category).is_("exited_at", "null").execute()
            count += 1
        except Exception as e:
            logger.warning("exit mark error %s/%s: %s", ticker, category, e)
    return count


def _enforce_dedup_in_db(client, all_matches: list[CategoryMatch], existing: dict, now: datetime) -> int:
    """크로스-런 dedup 일관성 보장: 이번 스캔에서 매칭된 종목의 비-dedup 카테고리 강제 종료.

    이전 실행에서 dedup으로 탈락한 카테고리가 다음 실행에서 다른 카테고리가 dedup 우승하면서
    재부활하는 oscillation 버그를 방지합니다.
    """
    # 이번 dedup 결과: ticker → kept categories
    dedup_by_ticker: dict[str, set[str]] = {}
    for m in all_matches:
        dedup_by_ticker.setdefault(m.ticker, set()).add(m.category)

    count = 0
    for ticker, kept_cats in dedup_by_ticker.items():
        # DB에서 이 ticker의 현재 active 카테고리 조회
        stale = [
            (t, c) for (t, c), row in existing.items()
            if t == ticker
            and row.get("exited_at") is None
            and c not in kept_cats
        ]
        for _, category in stale:
            try:
                client.table("hundredx_category_matches").update(
                    {"exited_at": now.isoformat()}
                ).eq("ticker", ticker).eq("category", category).is_("exited_at", "null").execute()
                count += 1
                logger.debug("Enforced dedup exit: %s/%s", ticker, category)
            except Exception as e:
                logger.warning("enforce_dedup exit error %s/%s: %s", ticker, category, e)
    return count


# ── Telegram alerts ───────────────────────────────────────────────────────────

def _send_alerts(client, new_matches: list[tuple[str, str, float, str | None]], all_matches_count: int = 0, total_active: int = 0, elapsed_sec: float = 0) -> None:
    """Send Telegram alerts for new category entries (deduped by alert_sent_at).

    new_matches: list of (ticker, category, confidence, analog_summary)
    """
    if not tg.is_enabled():
        logger.info("Telegram not configured — skipping alerts")
        return

    now = datetime.now(timezone.utc).isoformat()

    # Build rich match payload for notify_new_matches
    if new_matches:
        rich_matches = [
            {
                "ticker": ticker,
                "category": category,
                "confidence": confidence,
                "headline": analog or "",  # analog_summary as headline fallback
            }
            for ticker, category, confidence, analog in new_matches
        ]
        tg.notify_new_matches(rich_matches, total_scanned=all_matches_count)

    # Mark alert_sent_at
    for ticker, category, _, _ in new_matches:
        try:
            client.table("hundredx_category_matches").update(
                {"alert_sent_at": now}
            ).eq("ticker", ticker).eq("category", category).execute()
        except Exception as e:
            logger.warning("alert_sent_at update error %s/%s: %s", ticker, category, e)


# ── Main scan ─────────────────────────────────────────────────────────────────

def run(min_confidence: float = MIN_CONFIDENCE) -> int:
    """Run all 7 detectors across all active KR stocks. Returns total matches upserted."""
    client = get_client()
    now = datetime.now(timezone.utc)

    with pipeline_run(client, "hundredx") as (rows_out, _):
        # Pre-fetch library (one query, ~12 rows)
        lib = _load_library(client)
        pptr_rules = _extract_pptr_rules(lib)
        _upsert_pptr_rules(client, pptr_rules)
        logger.info("Library loaded: %d categories, %d stocks, %d PPTR rules",
                    len(lib), sum(len(v) for v in lib.values()), len(pptr_rules))
        # Fetch active KR + US stocks via pagination (bypassing PostgREST 1000 row hard limit)
        stocks = []
        page_size = 1000
        offset = 0
        while True:
            res = (
                client.table("stocks")
                .select("ticker, market, sector_tag")
                .eq("is_active", True)
                .in_("market", ["KOSPI", "KOSDAQ", "NYSE", "NASDAQ"])
                .range(offset, offset + page_size - 1)
                .execute()
            )
            data = res.data or []
            stocks.extend(data)
            if len(data) < page_size:
                break
            offset += page_size

        tickers = [s["ticker"] for s in stocks]
        sector_by_ticker = {s["ticker"]: s.get("sector_tag") for s in stocks}
        market_by_ticker = {s["ticker"]: s.get("market") for s in stocks}
        kr_count = sum(1 for s in stocks if s["market"] in ("KOSPI", "KOSDAQ"))
        us_count = len(stocks) - kr_count
        logger.info("Scanning %d active stocks (KR: %d, US: %d)", len(tickers), kr_count, us_count)
        # Pre-fetch all existing matches (for first_detected_at management)
        existing = _fetch_existing(client, tickers)
        active_before: set[tuple[str, str]] = {
            (r["ticker"], r["category"])
            for r in (existing.values())
            if r.get("exited_at") is None
        }

        all_matches: list[CategoryMatch] = []
        all_near_misses: list[dict] = []
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
                        
                        if ticker in ("083450", "082740"):
                            logger.info(f"[DEBUG HUNDREDX] Ticker {ticker} against detector {category} returned: {result}")
                            if result:
                                logger.info(f"[DEBUG HUNDREDX] Confidence: {result.confidence}, Min required: {min_confidence}")

                        if result is not None and result.confidence >= min_confidence:
                            result.ticker = ticker
                            result.category = category
                            # Fingerprint match: compare current signals to library precedent
                            fp = best_match_in_category(stock_data, f, _flatten_lib(lib), category)
                            if fp is not None:
                                result.fingerprint_score = fp.score
                                result.fingerprint_library_ticker = fp.library_ticker
                                result.fingerprint_dims = {
                                    "matched": fp.matched_dims,
                                    "missing": fp.missing_dims,
                                    "details": fp.details,
                                }
                            # Timeline progress: which trigger stage in best library timeline?
                            tl = best_timeline_in_category(stock_data, f, _flatten_lib(lib), category)
                            if tl is not None:
                                result.timeline_progress = progress_to_dict(tl)
                            all_matches.append(result)
                            active_after.add((ticker, category))
                    except Exception as e:
                        logger.warning("Detector %s error on %s: %s", category, ticker, e)

                # ── PPTR Detector (보완 탐지) ──
                try:
                    if pptr_rules:
                        pptr_filings_by_id = {
                            str(f.get("id") or f.get("source_id") or f.get("filed_at") or idx): f
                            for idx, f in enumerate(filings + filings_clinical)
                        }
                        pptr_filings = list(pptr_filings_by_id.values())
                        pptr_matches = detect_from_pptr(stock_data, pptr_filings, pptr_rules)
                        for pm in pptr_matches:
                            # 만약 동일 종목+카테고리가 이미 7개 디텍터에서 탐지되었다면 스킵
                            if (ticker, pm.category) not in active_after:
                                all_matches.append(pm)
                                active_after.add((ticker, pm.category))
                        if not pptr_matches:
                            all_near_misses.extend(
                                analyze_pptr_near_misses(stock_data, pptr_filings, pptr_rules)
                            )
                except Exception as e:
                    logger.warning("PPTR Detector error on %s: %s", ticker, e)

        # ── Category deduplication: keep best-confidence category per ticker ──
        # A single ticker firing all 7 categories dilutes signal quality.
        # Keep only the highest-confidence category per ticker; demote the rest.
        if all_matches:
            all_matches = _deduplicate_categories(all_matches)
            active_after = {(m.ticker, m.category) for m in all_matches}

        # Upsert all matches
        if all_matches:
            price_performances = _fetch_price_performances(all_matches, market_by_ticker)
            _upsert_matches_with_analogs(
                client,
                all_matches,
                existing,
                lib,
                now,
                price_performances=price_performances,
            )
            logger.info("Upserted %d category matches (after dedup)", len(all_matches))
        if all_near_misses:
            _insert_pptr_near_misses(client, all_near_misses, now)
            logger.info("Inserted %d PPTR near misses", len(all_near_misses))

        # 크로스-런 dedup 일관성: 이번에 매칭된 종목의 비-dedup 카테고리 강제 종료
        if all_matches:
            dedup_exits = _enforce_dedup_in_db(client, all_matches, existing, now)
            if dedup_exits:
                logger.info("Enforced dedup: exited %d stale categories", dedup_exits)

        # Mark exits (종목 자체가 사라진 경우)
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

        # Fetch total active count for summary
        try:
            active_res = (
                client.table("hundredx_category_matches")
                .select("ticker", count="exact")
                .is_("exited_at", "null")
                .execute()
            )
            total_active = active_res.count or len(all_matches)
        except Exception:
            total_active = len(all_matches)

        elapsed_sec = (datetime.now(timezone.utc) - now).total_seconds()

        if new_entries:
            _send_alerts(client, new_entries, all_matches_count=len(tickers), total_active=total_active, elapsed_sec=elapsed_sec)
            logger.info("Sent alerts for %d new entries", len(new_entries))

        # Send daily scanner summary (even if no new entries)
        try:
            top_for_summary = [
                {"ticker": t, "category": cat, "confidence": conf}
                for t, cat, conf, _ in sorted(new_entries, key=lambda x: -x[2])[:5]
            ] if new_entries else []
            updated_count = len(all_matches) - len(new_entries)
            tg.notify_scanner_summary(
                new_count=len(new_entries),
                updated_count=max(0, updated_count),
                total_active=total_active,
                elapsed_sec=elapsed_sec,
                top_matches=top_for_summary,
            )
        except Exception as e:
            logger.warning("Telegram summary failed: %s", e)

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
