"""PPTR Detector — 보완 디텍터.

라이브러리 PPTR의 Resolution에서 추출한 detector_rule을 현재 종목에 적용하여
기존 7개 디텍터가 놓친 종목이나 추가 근거를 확보합니다.
"""
from __future__ import annotations
from .models import CategoryMatch
from .keywords import _extract_amount_krw


def _kw_hit(text: str, keywords: list[str]) -> list[str]:
    text_lower = text.lower()
    return [kw for kw in keywords if kw.lower() in text_lower]


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

        if not target_category:
            continue

        # 1. Sector Check
        req_sector = conditions.get("sector_required")
        if req_sector and req_sector.lower() not in sector_tag:
            continue
            
        # 2. Quant Check
        # BCR
        bcr_min = conditions.get("bcr_at_signal")
        if bcr_min is not None:
            backlog = stock_data.get("order_backlog") or 0
            rev_ttm = stock_data.get("revenue_ttm") or stock_data.get("revenue") or 0
            curr_bcr = backlog / rev_ttm if rev_ttm > 0 else 0
            if curr_bcr < bcr_min:
                continue
                
        # OPM delta
        opm_delta_min = conditions.get("opm_delta_at_signal")
        if opm_delta_min is not None:
            opm_ttm = stock_data.get("op_margin_ttm")
            opm_prev = stock_data.get("op_margin_prev")
            if opm_ttm is None or opm_prev is None:
                continue
            if (opm_ttm - opm_prev) < opm_delta_min:
                continue
                
        # OPM min
        opm_min = conditions.get("opm_at_signal")
        if opm_min is not None:
            opm_ttm = stock_data.get("op_margin_ttm")
            if opm_ttm is None or opm_ttm < opm_min:
                continue

        # 3. Keyword Check
        req_keywords = conditions.get("keywords", [])
        min_kw = conditions.get("min_keyword_matches", 1)
        
        best_filing = None
        best_hits = []
        found_kw = False
        
        if req_keywords:
            for f, text in combined_texts:
                hits = _kw_hit(text, req_keywords)
                if len(hits) >= min_kw:
                    found_kw = True
                    if len(hits) > len(best_hits):
                        best_hits = hits
                        best_filing = f
            
            if not found_kw:
                continue
                
        # 4. Amount Check
        amt_th = conditions.get("amount_threshold_billions")
        if amt_th and best_filing:
            text = (best_filing.get("raw_text") or "") + " " + (best_filing.get("headline") or "")
            amt = _extract_amount_krw(text)
            if amt is None or amt < amt_th:
                continue

        # Passed all conditions -> Match
        evidence = []
        if best_filing:
            evidence.append({
                "source_type": "filing",
                "source_id": str(best_filing.get("id", "")),
                "text_excerpt": (best_filing.get("headline") or "")[:200],
                "date": best_filing.get("filed_at"),
                "amount": _extract_amount_krw((best_filing.get("raw_text") or "") + " " + (best_filing.get("headline") or "")) if amt_th else None,
            })
            evidence.append({
                "source_type": "keywords",
                "source_id": f"{ticker}_pptr_kw",
                "text_excerpt": f"PPTR 원인 매칭 ({library_ticker} PR): {', '.join(best_hits[:3])}",
                "date": best_filing.get("filed_at"),
                "amount": None,
            })
        else:
            evidence.append({
                "source_type": "quant",
                "source_id": f"{ticker}_pptr_quant",
                "text_excerpt": f"PPTR 정량 조건 매칭 ({library_ticker} PR)",
                "date": None,
                "amount": None,
            })
            
        matches.append(CategoryMatch(
            ticker=ticker,
            category=target_category,
            confidence=0.75, # PPTR base confidence
            evidence=evidence,
            pptr_match={
                "library_ticker": library_ticker,
                "producer_id": producer_id,
                "matched_conditions": list(conditions.keys())
            }
        ))
        
    return matches
