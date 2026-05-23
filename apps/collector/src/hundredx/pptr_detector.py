"""PPTR Detector — 보완 디텍터.

라이브러리 PPTR의 Resolution에서 추출한 detector_rule을 현재 종목에 적용하여
기존 7개 디텍터가 놓친 종목이나 추가 근거를 확보합니다.
"""
from __future__ import annotations
from .models import CategoryMatch
from .keywords import _extract_amount_krw
from .pptr_confidence import compute_pptr_confidence


SUPPORTED_CONDITION_KEYS = {
    "sector_required",
    "bcr_at_signal",
    "backlog_yoy_pct",
    "revenue_yoy_pct",
    "revenue_growth_yoy_pct",
    "opm_delta_at_signal",
    "opm_at_signal",
    "keywords",
    "min_keyword_matches",
    "amount_threshold_billions",
    "special",
}

ACTIONABLE_NON_SPECIAL_KEYS = SUPPORTED_CONDITION_KEYS - {"special", "min_keyword_matches"}
MIN_SPECIAL_ONLY_VOLUME_SPIKE_RATIO = 20.0
BLOCKED_PPTR_CATEGORIES = {"미분류", "단기_테마_급등"}


def _safe_float(value) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _kw_hit(text: str, keywords: list[str]) -> list[str]:
    text_lower = text.lower()
    return [kw for kw in keywords if kw.lower() in text_lower]


def _best_keyword_filing(
    combined_texts: list[tuple[dict, str]],
    keywords: list[str],
    min_hits: int,
) -> tuple[dict | None, list[str]]:
    best_filing = None
    best_hits: list[str] = []
    for filing, text in combined_texts:
        hits = _kw_hit(text, keywords)
        if len(hits) >= min_hits and len(hits) > len(best_hits):
            best_hits = hits
            best_filing = filing
    return best_filing, best_hits


def _best_amount_filing(combined_texts: list[tuple[dict, str]]) -> tuple[dict | None, float | None]:
    best_filing = None
    best_amount = None
    for filing, text in combined_texts:
        amount = _extract_amount_krw(text)
        if amount is None:
            amount = _safe_float(filing.get("parsed_amount"))
        if amount is None:
            continue
        if best_amount is None or amount > best_amount:
            best_amount = amount
            best_filing = filing
    return best_filing, best_amount


def _has_actionable_condition(conditions: dict) -> bool:
    if any(key in ACTIONABLE_NON_SPECIAL_KEYS for key in conditions):
        return True
    special = conditions.get("special") or {}
    if not isinstance(special, dict):
        return False
    spike_ratio = _safe_float(special.get("max_volume_spike_ratio"))
    has_required_spike = (
        special.get("volume_spike_required") is True
        and spike_ratio is not None
        and spike_ratio >= MIN_SPECIAL_ONLY_VOLUME_SPIKE_RATIO
    )
    return bool(
        special.get("news_keywords")
        or special.get("keywords")
        or has_required_spike
    )


def _has_non_special_condition(conditions: dict) -> bool:
    return any(key in ACTIONABLE_NON_SPECIAL_KEYS for key in conditions)


def detect_from_pptr(
    stock_data: dict, 
    filings: list[dict], 
    library_pptr_rules: list[dict]
) -> list[CategoryMatch]:
    matches = []
    ticker = stock_data.get("ticker", "")
    sector_tag = (stock_data.get("sector_tag") or "").lower()

    # Pre-process filings for keyword search
    combined_texts = []
    for f in filings:
        t = (f.get("raw_text") or "") + " " + (f.get("headline") or "")
        combined_texts.append((f, t))
    
    for rule in library_pptr_rules:
        library_ticker = rule.get("library_ticker")
        producer_id = rule.get("producer_id")
        target_category = rule.get("category")
        conditions = rule.get("conditions", {})

        if library_ticker and ticker == library_ticker:
            continue
        if not target_category:
            continue
        if target_category in BLOCKED_PPTR_CATEGORIES:
            continue
        if not _has_actionable_condition(conditions):
            continue
        has_non_special = _has_non_special_condition(conditions)
        matched_conditions: list[str] = []

        # 1. Sector Check
        req_sector = conditions.get("sector_required")
        if req_sector and req_sector.lower() not in sector_tag:
            continue
        if req_sector:
            matched_conditions.append("sector_required")
            
        # 2. Quant Check
        # BCR
        bcr_min = conditions.get("bcr_at_signal")
        if bcr_min is not None:
            backlog = stock_data.get("order_backlog") or 0
            rev_ttm = stock_data.get("revenue_ttm") or stock_data.get("revenue") or 0
            curr_bcr = backlog / rev_ttm if rev_ttm > 0 else 0
            if curr_bcr < bcr_min:
                continue
            matched_conditions.append("bcr_at_signal")

        # Backlog YoY growth
        backlog_yoy_min = conditions.get("backlog_yoy_pct")
        if backlog_yoy_min is not None:
            backlog = stock_data.get("order_backlog")
            backlog_prev = stock_data.get("order_backlog_prev")
            if backlog is None or backlog_prev is None or backlog_prev <= 0:
                continue
            backlog_yoy = (backlog - backlog_prev) / backlog_prev * 100
            if backlog_yoy < backlog_yoy_min:
                continue
            matched_conditions.append("backlog_yoy_pct")

        # Revenue YoY growth
        revenue_yoy_min = conditions.get("revenue_yoy_pct") or conditions.get("revenue_growth_yoy_pct")
        if revenue_yoy_min is not None:
            rev_ttm = stock_data.get("revenue_ttm")
            rev_prev = stock_data.get("revenue_prev")
            if rev_ttm is None or rev_prev is None or rev_prev <= 0:
                continue
            revenue_yoy = (rev_ttm - rev_prev) / rev_prev * 100
            if revenue_yoy < revenue_yoy_min:
                continue
            matched_conditions.append(
                "revenue_yoy_pct"
                if "revenue_yoy_pct" in conditions
                else "revenue_growth_yoy_pct"
            )
                
        # OPM delta
        opm_delta_min = conditions.get("opm_delta_at_signal")
        if opm_delta_min is not None:
            if opm_delta_min <= 0:
                continue
            opm_ttm = stock_data.get("op_margin_ttm")
            opm_prev = stock_data.get("op_margin_prev")
            if opm_ttm is None or opm_prev is None:
                continue
            if (opm_ttm - opm_prev) < opm_delta_min:
                continue
            matched_conditions.append("opm_delta_at_signal")
                
        # OPM min
        opm_min = conditions.get("opm_at_signal")
        if opm_min is not None:
            opm_ttm = stock_data.get("op_margin_ttm")
            if opm_ttm is None or opm_ttm < opm_min:
                continue
            matched_conditions.append("opm_at_signal")

        # 3. Keyword Check
        req_keywords = conditions.get("keywords", [])
        min_kw = conditions.get("min_keyword_matches", 1)
        
        best_filing = None
        best_hits = []
        found_kw = False
        
        if req_keywords:
            best_filing, best_hits = _best_keyword_filing(combined_texts, req_keywords, min_kw)
            found_kw = len(best_hits) >= min_kw
            
            if not found_kw:
                continue
            matched_conditions.append("keywords")
                
        # 4. Amount Check
        amt_th = conditions.get("amount_threshold_billions")
        best_amount = None
        if amt_th:
            if best_filing:
                text = (best_filing.get("raw_text") or "") + " " + (best_filing.get("headline") or "")
                best_amount = _extract_amount_krw(text) or _safe_float(best_filing.get("parsed_amount"))
            else:
                best_filing, best_amount = _best_amount_filing(combined_texts)
            if best_amount is None or best_amount < amt_th:
                continue
            matched_conditions.append("amount_threshold_billions")

        # 5. Special PPTR conditions
        special = conditions.get("special") or {}
        special_keywords = special.get("news_keywords") or special.get("keywords") or []
        has_special_keywords = bool(special_keywords)
        special_min_kw = int(special.get("news_macro_hits") or special.get("min_keyword_matches") or 0)
        if special_keywords:
            special_min_kw = max(1, min(special_min_kw or 1, len(special_keywords)))
            special_filing, special_hits = _best_keyword_filing(combined_texts, special_keywords, special_min_kw)
            if len(special_hits) < special_min_kw:
                continue
            if not best_filing or len(special_hits) > len(best_hits):
                best_filing = special_filing
                best_hits = special_hits
            matched_conditions.append("special")

        volume_spike_min = special.get("max_volume_spike_ratio")
        if volume_spike_min is not None:
            if (
                not has_non_special
                and not has_special_keywords
                and (
                    special.get("volume_spike_required") is not True
                    or volume_spike_min < MIN_SPECIAL_ONLY_VOLUME_SPIKE_RATIO
                )
            ):
                continue
            current_spike = stock_data.get("max_volume_spike_ratio") or stock_data.get("volume_spike_ratio")
            if current_spike is None or current_spike < volume_spike_min:
                continue
            if "special" not in matched_conditions:
                matched_conditions.append("special")

        # 퀀트 조건만 통과했고 키워드/파일링 증거가 없으면 스킵
        # (BCR/OPM/revenue 수치만으로 모든 카테고리 발화하는 광범위 매칭 방지)
        has_keyword_evidence = bool(best_filing or (has_special_keywords and len(best_hits) > 0))
        if not has_keyword_evidence:
            continue

        # Passed all conditions -> Match
        evidence = []
        if best_filing:
            text = (best_filing.get("raw_text") or "") + " " + (best_filing.get("headline") or "")
            evidence.append({
                "source_type": "filing",
                "source_id": str(best_filing.get("id", "")),
                "text_excerpt": (best_filing.get("headline") or "")[:200],
                "date": best_filing.get("filed_at"),
                "amount": (_extract_amount_krw(text) or _safe_float(best_filing.get("parsed_amount"))) if amt_th else None,
            })
            evidence.append({
                "source_type": "keywords",
                "source_id": f"{ticker}_pptr_kw",
                "text_excerpt": f"PPTR 원인 매칭 ({library_ticker} PR): {', '.join(best_hits[:3])}",
                "date": best_filing.get("filed_at"),
                "amount": None,
            })
        else:
            source_type = "volume_spike" if volume_spike_min is not None else "quant"
            source_id_suffix = "pptr_volume" if volume_spike_min is not None else "pptr_quant"
            text_excerpt = (
                f"PPTR volume spike match ({library_ticker} PR): >= {volume_spike_min}x"
                if volume_spike_min is not None
                else f"PPTR quant match ({library_ticker} PR)"
            )
            evidence.append({
                "source_type": source_type,
                "source_id": f"{ticker}_{source_id_suffix}",
                "text_excerpt": text_excerpt,
                "date": None,
                "amount": volume_spike_min,
            })
            
        confidence, confidence_breakdown = compute_pptr_confidence(
            rule=rule,
            matched_conditions=matched_conditions,
            evidence=evidence,
            stock_data=stock_data,
        )

        matches.append(CategoryMatch(
            ticker=ticker,
            category=target_category,
            confidence=confidence,
            evidence=evidence,
            pptr_match={
                "library_ticker": library_ticker,
                "producer_id": producer_id,
                "rule_id": rule.get("rule_id"),
                "matched_conditions": matched_conditions,
                "candidate_conditions": list(conditions.keys()),
                "confidence_breakdown": confidence_breakdown,
            }
        ))
        
    return matches
