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


# ── Convergent boost signals (Seyhun 1988, O'Neil CANSLIM S) ───────────────
# 임원 매수 + 자사주 매입은 카테고리 무관한 강한 "내부자 확신" 신호.
# Seyhun 1988: 임원 매수 후 12개월 평균 초과수익률 +8.7%.
# O'Neil S: 발행주식 감소 = 자사주 매입 = 100배 종목 공통 패턴.
# 매칭된 카테고리의 confidence에 +0.05 부스트 (최대 0.95 캡).
_INSIDER_BUY_KEYWORDS = [
    "임원 ・ 주요주주 특정증권", "임원 주식 취득", "임원이 취득",
    "최대주주 장내매수", "최대주주 등 소유주식 변동",
    "대표이사 매수", "대표이사 장내매수",
    "특수관계인 매수", "특수관계인 장내매수",
    "임원 ․ 주요주주", "임원·주요주주",
]
_BUYBACK_KEYWORDS = [
    "자기주식 취득", "자사주 취득", "자사주 매입",
    "자기주식취득", "자기주식 소각", "자사주 소각",
    "자사주매입", "자기주식취득 신탁계약",
]


# ── Sector × Category deny matrix ─────────────────────────────────────────
# 라이브러리 49개 종목 sector × category 분포에서 도출한 명백한 비현실적 조합.
# 한 카테고리가 "이 섹터에서는 절대 안 일어남"인 경우만 차단 (보수적).
# 예: 조선 회사가 임상 파이프라인을 가질 수 없음 / 바이오 회사가 조선 슈퍼사이클을 탈 수 없음.
# 키워드는 sector_tag/sector_wics에 contains() 매칭.
_SECTOR_DENY_MATRIX: dict[str, list[str]] = {
    "임상_파이프라인": [
        "조선", "엔진", "방산", "건설", "pcb",
        "이차전지", "배터리", "철강", "유틸리티", "통신",
        "자동차부품", "전력기기", "반도체",
    ],
    "조선_슈퍼사이클": [
        "바이오", "제약", "임상", "반도체", "pcb",
        "이차전지", "배터리", "자동차부품", "게임", "유통",
    ],
    "이차전지_소재": [
        "바이오", "제약", "임상", "조선", "엔진",
        "방산", "건설", "pcb", "게임",
    ],
    "빅테크_파트너": [
        "바이오", "제약", "임상", "조선", "건설",
        "철강", "유틸리티", "유통", "운송",
    ],
    "공급_병목": [
        "바이오", "제약", "임상", "게임", "유통", "엔터테인먼트",
    ],
    "플랫폼_독점": [
        "조선", "엔진", "건설", "철강", "유틸리티",
    ],
}


def _category_blocked_by_sector(category: str, sector_tag: str | None) -> bool:
    """Return True if (category, sector) is in deny matrix — block detector."""
    if not sector_tag:
        return False  # 섹터 미상은 통과 (보수적)
    deny = _SECTOR_DENY_MATRIX.get(category, [])
    sect_lower = sector_tag.lower()
    return any(kw in sect_lower for kw in deny)


def _count_convergent_signals(filings: list[dict]) -> dict:
    """Count insider buy / buyback filings — multiple events = stronger signal.

    Returns dict:
      {"insider_buy": int, "buyback": int, "cluster": bool, "labels": [str, ...]}

    cluster=True 의 정의: 임원매수가 2건 이상 OR 임원매수+자사주매입 동시 발생.
    Seyhun(1988): "cluster buying" (다중 인사이더 매수) 효과 +12% 초과수익 (단건 +8.7%).
    """
    insider = 0
    buyback = 0
    for f in filings:
        text = ((f.get("raw_text") or "") + " " + (f.get("headline") or "")).lower()
        if any(kw.lower() in text for kw in _INSIDER_BUY_KEYWORDS):
            insider += 1
        elif any(kw.lower() in text for kw in _BUYBACK_KEYWORDS):
            buyback += 1
    labels = []
    if insider > 0: labels.append(f"insider_buy×{insider}")
    if buyback > 0: labels.append(f"buyback×{buyback}")
    cluster = insider >= 2 or (insider >= 1 and buyback >= 1)
    return {
        "insider_buy": insider,
        "buyback": buyback,
        "cluster": cluster,
        "labels": labels,
    }


def _has_convergent_signal(filings: list[dict]) -> tuple[bool, str | None]:
    """Backwards-compat thin wrapper used in places that don't need counts."""
    c = _count_convergent_signals(filings)
    if c["cluster"]: return True, "cluster"
    if c["insider_buy"] > 0: return True, "insider_buy"
    if c["buyback"] > 0: return True, "buyback"
    return False, None


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
                    "price_performance_updated_at, evidence"
                )
                .in_("ticker", chunk)
                .execute()
            )
            if res.data:
                rows.extend(res.data)
        except Exception as e:
            logger.warning("Error fetching existing matches chunk: %s", e)

    return {(r["ticker"], r["category"]): r for r in rows}


# ── LLM verdict helpers ───────────────────────────────────────────────────────

def _get_llm_verdict(row: dict | None) -> str | None:
    """evidence JSONB에서 LLM 검증 결과 추출.

    Returns: "confirm" | "reject" | "uncertain" | None (미검증)
    """
    if not row:
        return None
    for ev in (row.get("evidence") or []):
        if isinstance(ev, dict) and ev.get("source_type") == "llm_verdict":
            text = ev.get("text_excerpt", "")
            if "LLM confirm" in text:
                return "confirm"
            if "LLM reject" in text:
                return "reject"
            if "LLM uncertain" in text:
                return "uncertain"
    return None


def _merge_llm_evidence(existing_evidence: list, new_evidence: list) -> list:
    """새 scanner evidence에 기존 LLM 판단 evidence를 보존해서 병합.

    LLM 검증 결과는 재스캔 시 덮어써지면 안 된다.
    """
    llm_entries = [
        ev for ev in (existing_evidence or [])
        if isinstance(ev, dict) and ev.get("source_type") == "llm_verdict"
    ]
    if not llm_entries:
        return new_evidence
    # llm_verdict는 맨 뒤에 보존 (scanner evidence + llm entries)
    non_llm_new = [
        ev for ev in (new_evidence or [])
        if not (isinstance(ev, dict) and ev.get("source_type") == "llm_verdict")
    ]
    return non_llm_new + llm_entries


# ── Filings batch fetch ───────────────────────────────────────────────────────

# 자본조달/지배구조 공시는 사업 시그널이 아니다.
# 본문에 사업/빅테크/임상 키워드가 등장하더라도 그건 회사 소개·자금 사용처 설명일 뿐
# detector를 트리거해선 안 된다 (LLM 검증 단계에서 일관되게 reject되는 패턴).
# 2026-05-25 LLM 검증으로 식별된 4건 모두 이 패턴:
#   017860 DS단석, 059270 해성에어로 (전환사채 → 빅테크_파트너 오탐)
#   139480 이마트, 005440 현대지에프홀딩스 (주식교환 → 임상_파이프라인 오탐)
_CORPORATE_FINANCE_HEADLINE_PATTERNS = (
    "전환사채권발행결정",
    "신주인수권부사채권발행결정",
    "교환사채권발행결정",
    "유상증자결정",
    "무상증자결정",
    "주식교환",
    "주식이전",
    "주식분할",
    "주식병합",
    "대량보유상황보고서",
    "임원ㆍ주요주주특정증권",
    "임원·주요주주특정증권",
    "최대주주변경",
    "자기주식취득",
    "자기주식처분",
)


def _is_corporate_finance_filing(headline: str | None) -> bool:
    if not headline:
        return False
    return any(pat in headline for pat in _CORPORATE_FINANCE_HEADLINE_PATTERNS)


def _fetch_filings_90d(client, tickers: list[str]) -> dict[str, list[dict]]:
    """Bulk-fetch filings from last 90 days for a batch of tickers.

    자본조달/지배구조 공시(CB·유증·주식교환·대량보유 등)는 사업 시그널이 아니므로
    detector 입력에서 제외한다.
    """
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
        if _is_corporate_finance_filing(row.get("headline")):
            continue
        result.setdefault(row["ticker"], []).append(row)
    return result


def _fetch_filings_2y(client, tickers: list[str]) -> dict[str, list[dict]]:
    """Bulk-fetch last 2 business-signal filings per ticker for clinical_pipe."""
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
        if _is_corporate_finance_filing(row.get("headline")):
            continue
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
        existing_row = existing.get((m.ticker, m.category))
        llm_verdict = _get_llm_verdict(existing_row)

        # LLM reject 보호: 한번 reject된 (ticker, category)는 재스캔해도 재진입 불가
        # (재진입하려면 verify-stocks로 override 필요)
        if llm_verdict == "reject":
            logger.debug("LLM reject guard: skipping %s/%s", m.ticker, m.category)
            continue

        fda = _resolve_first_detected(m, existing, now)
        pptr_match = getattr(m, "pptr_match", None)
        pptr_rule_id = pptr_match.get("rule_id") if pptr_match else None
        pptr_breakdown = pptr_match.get("confidence_breakdown") if pptr_match else None

        # Resolve analog from fingerprint match if present, else fallback
        if m.fingerprint_library_ticker:
            analog = _find_lib_entry(lib, m.fingerprint_library_ticker, m.category)
        else:
            analog = _get_analog(lib, m)

        perf = price_performances.get(m.ticker)
        # LLM confirm/uncertain 보호: evidence에서 llm_verdict 항목 보존
        evidence = _merge_llm_evidence(
            existing_row.get("evidence") if existing_row else None,
            m.evidence,
        )

        row = {
            "ticker": m.ticker,
            "category": m.category,
            "confidence": round(m.confidence, 3),
            "evidence": evidence,
            "first_detected_at": fda.isoformat(),
            "detected_at": now.isoformat(),
            "exited_at": None,
            "analog_ticker": analog.get("ticker") if analog else None,
            "analog_date": analog.get("rise_start_date") if analog else None,
            "analog_multiplier": analog.get("peak_multiplier") if analog else None,
            "fingerprint_score": (
                round(m.fingerprint_score, 3) if m.fingerprint_score is not None else None
            ),
            "fingerprint_library_ticker": getattr(m, "fingerprint_library_ticker", None),
            "fingerprint_dims": m.fingerprint_dims,
            "convergent_signals": getattr(m, "convergent_signals", None),
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
# ⚠️  2026-05-24: 평가 데이터 기반 결정 — 수익성_급전환 제거
#     평가 인프라 측정 결과 수익성_급전환은 labeled 15건 중 0건 confirm.
#     recall에는 기여하지만 같은 종목을 다른 detector가 이미 catch (per_detector @90d).
#     ALWAYS_KEEP 유지 시 false-positive 다수 → labeled set 오염.
#     제거 시: 다른 카테고리 fire 종목에선 흡수 (precision↑), 단독 fire 종목에서만 alert (recall 유지).
# ⚠️  임상_파이프라인은 _ALWAYS_KEEP에서 제거:
#     clinical_pipe.py에 비바이오 섹터 early-exit가 추가됐으므로, 비바이오 종목에서
#     임상이 탐지됐다면 detector 버그 → dedup으로 제거되어야 함.
_ALWAYS_KEEP_CATEGORIES: frozenset[str] = frozenset()

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

def _mark_exits(
    client,
    active_before: set[tuple[str, str]],
    active_after: set[tuple[str, str]],
    now: datetime,
    existing: dict | None = None,
) -> int:
    """Set exited_at for (ticker, category) pairs that disappeared this scan.

    LLM-confirmed 종목은 스캐너가 재탐지 못해도 강제 종료하지 않는다.
    (시그널 지속 여부는 LLM 재검증으로만 변경)
    """
    exited = active_before - active_after
    if not exited:
        return 0
    count = 0
    for ticker, category in exited:
        # LLM confirm 보호: 검증 완료된 종목은 스캐너가 못 잡아도 유지
        if existing:
            row = existing.get((ticker, category))
            if _get_llm_verdict(row) == "confirm":
                logger.debug("LLM confirm guard: skipping exit %s/%s", ticker, category)
                continue
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
            # LLM confirm 보호: dedup에서도 강제 종료 안 함
            and _get_llm_verdict(row) != "confirm"
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

        # Library self-match guard: (ticker, category) pairs that already exist in library.
        # We skip these so that a library stock is not re-detected by its OWN historical criteria.
        # (PPTR detector has the same guard; this extends it to keyword/filing detectors.)
        lib_match_set: set[tuple[str, str]] = {
            (row["ticker"], row["category"])
            for rows in lib.values()
            for row in rows
        }
        # Fetch active KR + US stocks via pagination (bypassing PostgREST 1000 row hard limit)
        stocks = []
        page_size = 1000
        offset = 0
        while True:
            res = (
                client.table("stocks")
                .select("ticker, market, sector_tag, market_cap")
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
        mktcap_by_ticker = {s["ticker"]: s.get("market_cap") for s in stocks}
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
                stock_data["market_cap"] = mktcap_by_ticker.get(ticker)

                # ── Market cap gate (data-driven from library distribution) ────
                # 자체 라이브러리(reliable post-2015, n=63) market_cap_at_signal 분포 기반:
                #   KOSPI  p10=527억  p25=2,174억  median=8,697억  p90=10조
                #   KOSDAQ p10=185억  p25=480억   median=2,643억  p90=10,914억
                # Mayer(2015) median $500M ≈ 7,000억 KRW, Bessembinder(2018) small-but-not-micro.
                # 라이브러리 capture:  KOSPI 82% / KOSDAQ 96%. (이전 게이트: 62% / 71%)
                # 차단 사례(차단되면 안 되는 진짜 100배): 101360(40억→295×), 005070(706억→109×) 등.
                mkt = market_by_ticker.get(ticker)
                mc = stock_data["market_cap"]
                if mc is not None and mkt in ("KOSPI", "KOSDAQ"):
                    max_mc = 5_000_000_000_000 if mkt == "KOSPI" else 2_000_000_000_000
                    min_mc =    50_000_000_000 if mkt == "KOSPI" else     5_000_000_000
                    if mc > max_mc or mc < min_mc:
                        continue

                filings = filings_90d.get(ticker, [])
                filings_clinical = filings_2y.get(ticker, [])

                for category, detector_fn in DETECTORS:
                    # ── Sector × category deny matrix ──
                    # 명백한 비현실적 조합은 detector 호출 전 차단 (CPU 절약 + FP 차단).
                    if _category_blocked_by_sector(category, stock_data.get("sector_tag")):
                        continue
                    try:
                        # clinical_pipe gets 2-year filings; others get 90d
                        f = filings_clinical if category == "임상_파이프라인" else filings
                        result = detector_fn(stock_data, f)
                        
                        if ticker in ("083450", "082740"):
                            logger.info(f"[DEBUG HUNDREDX] Ticker {ticker} against detector {category} returned: {result}")
                            if result:
                                logger.info(f"[DEBUG HUNDREDX] Confidence: {result.confidence}, Min required: {min_confidence}")

                        if result is not None and result.confidence >= min_confidence:
                            # Library self-match guard: skip if this exact (ticker, category)
                            # is already registered in the library as a historical precedent.
                            if (ticker, category) in lib_match_set:
                                logger.debug(
                                    "Library self-match skipped: %s/%s", ticker, category
                                )
                                continue

                            # ── Piotroski F-Score 품질 게이트 (DART TTM 보정 후 캘리브레이션) ─
                            # 라이브러리 100배 종목 분포 (TTM-from-cumulative 적용 후):
                            #   median = 1, p25 = 0, p75 = 3 — 한국 100배는 pre-profitability 단계 다수.
                            # 그래도 F-Score 0은 모든 지표 악화 → 거의 확실히 FP.
                            #   F == 0 (모두 악화): ×0.7
                            #   F >= 4 (상위 ~20%): +0.05 부스트
                            # 임상_파이프라인은 R&D 적자 페이즈 정상 → 면제.
                            f_score = stock_data.get("f_score")
                            if f_score is not None and category != "임상_파이프라인":
                                if f_score == 0:
                                    result.confidence = round(result.confidence * 0.7, 3)
                                    if result.confidence < min_confidence:
                                        continue
                                elif f_score >= 4:
                                    result.confidence = round(min(0.95, result.confidence + 0.05), 3)

                            # ── Sloan accruals 게이트 (CFO > NI = clean earnings) ──
                            # 라이브러리 58%가 음수 accruals (현금이익 우수). 양수 큰 값은 회계조정 의심.
                            accruals = stock_data.get("accruals_ratio")
                            if accruals is not None:
                                if accruals < 0:
                                    # CFO > NI: clean earnings, multibagger 친화적 패턴
                                    result.confidence = round(min(0.95, result.confidence + 0.03), 3)
                                elif accruals > 0.15:
                                    # 과도한 발생주의 — 회계이익 의심
                                    result.confidence = round(result.confidence * 0.85, 3)

                            # ── Convergent insider/buyback boost (Seyhun/O'Neil) ──
                            # 단건 임원매수/자사주매입: +0.03
                            # cluster (2건 이상 OR 임원+자사주 동시): +0.07 (Seyhun cluster effect)
                            conv = _count_convergent_signals(f)
                            if conv["cluster"]:
                                result.confidence = round(min(0.95, result.confidence + 0.07), 3)
                            elif conv["insider_buy"] > 0 or conv["buyback"] > 0:
                                result.confidence = round(min(0.95, result.confidence + 0.03), 3)
                            if conv["labels"]:
                                try:
                                    result.convergent_signals = conv["labels"]
                                except Exception:
                                    pass

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
        exits = _mark_exits(client, active_before, active_after, now, existing=existing)
        if exits:
            logger.info("Marked %d exits", exits)

        # Library self-match cleanup: exit any active matches that are in the library
        # (These can persist from before the self-match guard was added, or from edge cases)
        self_match_exits = 0
        for (ticker, category) in list(active_after):
            if (ticker, category) in lib_match_set:
                try:
                    client.table("hundredx_category_matches").update(
                        {"exited_at": now}
                    ).eq("ticker", ticker).eq("category", category).is_("exited_at", None).execute()
                    self_match_exits += 1
                    logger.debug("Self-match cleanup: exited %s/%s", ticker, category)
                except Exception as e:
                    logger.warning("Self-match cleanup error %s/%s: %s", ticker, category, e)
        if self_match_exits:
            logger.info("Library self-match cleanup: exited %d stale entries", self_match_exits)

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
