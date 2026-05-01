"""Timeline matching — track which trigger sequence stage a current stock is in.

Concept: 100x stocks rise through a SEQUENCE of triggers, not a single moment.
For each library stock, we encode its trigger sequence (T-12mo, T-9mo, ..., T+9mo).
For each current stock, we evaluate which triggers in each library timeline have
already fired, and at what dates.

Output: TimelineProgress
  - For the best-matching library timeline:
    - List of fired triggers (which seq, when fired, how many months ago)
    - Trajectory score = weighted sum of fired triggers / total weight
    - Current position in months relative to library's rise_start
    - Next expected trigger + months until expected

The "fired" detection per trigger:
  - quant signals: stock_data quant matches trigger.signals.quant within tolerance
  - keyword signals: filings within last N months contain matched keywords
  - amount signals: any filing has parsed_amount >= threshold
  - sector signals: stocks.sector_tag matches required
"""
from __future__ import annotations
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from .fingerprint_match import _compute_current_quant, _QUANT_FIELD_TO_STOCK_KEY, _QUANT_TOLERANCE

logger = logging.getLogger(__name__)


@dataclass
class FiredTrigger:
    seq: int
    name: str
    months_from_rise: int
    weight: float
    fired_at_date: str | None = None         # earliest filing date that fired this trigger
    fired_at_months_ago: float | None = None
    matched_signals: list[str] = field(default_factory=list)


@dataclass
class TimelineProgress:
    library_ticker: str
    library_category: str
    library_peak_multiplier: float | None
    fired_triggers: list[FiredTrigger]
    total_triggers: int
    trajectory_score: float                 # 0.0 - 1.0 (weighted)
    current_position_months: int            # estimated position in library timeline (rise_start = T0)
    next_expected: dict | None = None        # {seq, name, expected_in_months}


def _signals_quant_match(quant_req: dict, current_quant: dict) -> tuple[bool, list[str]]:
    """Returns (all_passed, matched_field_names)."""
    matched: list[str] = []
    for field_name, lib_value in quant_req.items():
        stock_key = _QUANT_FIELD_TO_STOCK_KEY.get(field_name, field_name)
        current_value = current_quant.get(stock_key)
        if current_value is None:
            return False, matched
        if field_name == "opm_prev":
            ok = current_value <= lib_value * (1 + _QUANT_TOLERANCE)
        else:
            ok = current_value >= lib_value * (1 - _QUANT_TOLERANCE)
        if not ok:
            return False, matched
        matched.append(field_name)
    return True, matched


def _signals_keyword_match(
    keywords: list[str], min_matches: int, filings: list[dict],
    months_back: int = 12
) -> tuple[bool, str | None, list[str]]:
    """Check if at least min_matches keywords appear across filings within months_back.

    Returns (passed, earliest_filing_date_with_match, matched_keywords).
    """
    if not keywords or not filings:
        return False, None, []

    # Filter filings to recent window
    cutoff = (datetime.utcnow() - timedelta(days=int(months_back * 30.5))).isoformat()
    recent = [f for f in filings if (f.get("filed_at") or "") >= cutoff]
    if not recent:
        return False, None, []

    # Find earliest filing where >=1 keyword appears + collect all matched keywords
    earliest_match_date: str | None = None
    all_matched: set[str] = set()
    # filings order: scanner provides them sorted by filed_at desc; iterate from oldest
    for f in sorted(recent, key=lambda x: x.get("filed_at") or ""):
        text = ((f.get("raw_text") or "") + " " + (f.get("headline") or "")).lower()
        matched_here = [kw for kw in keywords if kw.lower() in text]
        if matched_here:
            if earliest_match_date is None:
                earliest_match_date = f.get("filed_at")
            all_matched.update(matched_here)

    passed = len(all_matched) >= min_matches
    return passed, earliest_match_date, sorted(all_matched)


def _check_trigger_fired(
    trigger: dict, stock_data: dict, current_quant: dict, filings: list[dict]
) -> tuple[bool, FiredTrigger | None]:
    """Determine if a single trigger has fired for the current stock.

    A trigger fires when ALL specified signals (quant + keyword + sector + amount) pass.
    """
    signals = trigger.get("signals", {}) or {}
    matched_dims: list[str] = []
    earliest_keyword_date: str | None = None

    # Sector check
    sector_required = signals.get("sector_required")
    if sector_required:
        if stock_data.get("sector_tag") != sector_required:
            return False, None
        matched_dims.append(f"sector={sector_required}")

    # Quant check
    quant_req = signals.get("quant")
    if quant_req:
        ok, q_matched = _signals_quant_match(quant_req, current_quant)
        if not ok:
            return False, None
        matched_dims.extend(f"quant.{f}" for f in q_matched)

    # Keyword check
    keywords = signals.get("keywords") or []
    if keywords:
        min_matches = signals.get("min_keyword_matches", 1)
        ok, earliest_date, kw_matched = _signals_keyword_match(keywords, min_matches, filings)
        if not ok:
            return False, None
        earliest_keyword_date = earliest_date
        matched_dims.append(f"keywords({len(kw_matched)}/{len(keywords)})")

    # Amount check
    amount_threshold = signals.get("amount_threshold_billions")
    if amount_threshold:
        any_match = False
        for f in filings:
            amount = f.get("parsed_amount")
            if amount is not None and amount >= amount_threshold:
                any_match = True
                if not earliest_keyword_date or (f.get("filed_at") or "") < earliest_keyword_date:
                    earliest_keyword_date = f.get("filed_at")
                break
        if not any_match:
            return False, None
        matched_dims.append(f"amount>={amount_threshold}억")

    # Compute "fired_at_months_ago"
    fired_at_months_ago: float | None = None
    if earliest_keyword_date:
        try:
            fired_dt = datetime.fromisoformat(earliest_keyword_date.replace("Z", "+00:00").split("T")[0])
            delta_days = (datetime.utcnow() - fired_dt).days
            fired_at_months_ago = round(delta_days / 30.5, 1)
        except (ValueError, AttributeError):
            pass

    return True, FiredTrigger(
        seq=trigger.get("seq", 0),
        name=trigger.get("name", ""),
        months_from_rise=trigger.get("months_from_rise", 0),
        weight=trigger.get("weight", 1.0),
        fired_at_date=earliest_keyword_date,
        fired_at_months_ago=fired_at_months_ago,
        matched_signals=matched_dims,
    )


def evaluate_timeline(
    stock_data: dict,
    filings: list[dict],
    library_entry: dict,
) -> TimelineProgress | None:
    """For one library entry with triggers timeline, evaluate current stock's position."""
    triggers = library_entry.get("triggers") or []
    if not triggers:
        return None

    current_quant = _compute_current_quant(stock_data)

    fired: list[FiredTrigger] = []
    for trigger in triggers:
        ok, ft = _check_trigger_fired(trigger, stock_data, current_quant, filings)
        if ok and ft:
            fired.append(ft)

    if not fired:
        return None

    total_weight = sum(t.get("weight", 1.0) for t in triggers)
    fired_weight = sum(t.weight for t in fired)
    trajectory_score = fired_weight / total_weight if total_weight > 0 else 0.0

    # Estimated current position: highest fired seq → its months_from_rise
    fired_sorted = sorted(fired, key=lambda f: f.seq)
    latest_fired = fired_sorted[-1]
    current_position = latest_fired.months_from_rise

    # Next expected trigger
    next_expected = None
    for trigger in sorted(triggers, key=lambda t: t.get("seq", 0)):
        if trigger.get("seq", 0) > latest_fired.seq:
            expected_months = trigger.get("months_from_rise", 0) - current_position
            next_expected = {
                "seq": trigger.get("seq"),
                "name": trigger.get("name"),
                "months_from_rise": trigger.get("months_from_rise"),
                "expected_in_months": expected_months,
            }
            break

    return TimelineProgress(
        library_ticker=library_entry.get("ticker", "?"),
        library_category=library_entry.get("category", "?"),
        library_peak_multiplier=library_entry.get("peak_multiplier"),
        fired_triggers=fired_sorted,
        total_triggers=len(triggers),
        trajectory_score=round(trajectory_score, 3),
        current_position_months=current_position,
        next_expected=next_expected,
    )


def best_timeline_in_category(
    stock_data: dict,
    filings: list[dict],
    library_entries: list[dict],
    category: str,
) -> TimelineProgress | None:
    """Pick the library timeline (in `category`) where current stock has highest trajectory_score."""
    candidates = [e for e in library_entries if e.get("category") == category and e.get("triggers")]
    if not candidates:
        return None
    progresses = [evaluate_timeline(stock_data, filings, e) for e in candidates]
    progresses = [p for p in progresses if p is not None]
    if not progresses:
        return None
    return max(progresses, key=lambda p: p.trajectory_score)


def progress_to_dict(p: TimelineProgress) -> dict:
    """Serialize for JSONB storage."""
    return {
        "library_ticker": p.library_ticker,
        "library_category": p.library_category,
        "library_peak_multiplier": float(p.library_peak_multiplier) if p.library_peak_multiplier else None,
        "fired_triggers": [
            {
                "seq": t.seq, "name": t.name,
                "months_from_rise": t.months_from_rise,
                "fired_at_date": t.fired_at_date,
                "fired_at_months_ago": t.fired_at_months_ago,
                "weight": t.weight,
                "matched_signals": t.matched_signals,
            }
            for t in p.fired_triggers
        ],
        "total_triggers": p.total_triggers,
        "trajectory_score": p.trajectory_score,
        "current_position_months": p.current_position_months,
        "next_expected": p.next_expected,
    }
