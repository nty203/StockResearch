"""PPTR Engine for HundredX Library.

Generates a 7-step PPTR (Predicate-Producer-Trace-Resolution) analysis from a library stock's historical data.
"""
from __future__ import annotations
from datetime import datetime, timezone
import json


def _safe_float(val, default=0.0) -> float:
    try:
        return float(val) if val is not None else default
    except (ValueError, TypeError):
        return default


def generate_pptr(library_row: dict) -> dict:
    """라이브러리 종목 1행 → PPTR 7단계 분석 JSON 생성.

    입력:
    - library_row: DB의 hundredx_library_stocks 테이블의 1개 row 딕셔너리
      (필수 키: ticker, category, pre_rise_signals, triggers, peak_multiplier, rise_start_date, notes)

    출력:
    - PPTR 7단계 JSON 구조체
    """
    ticker = library_row.get("ticker", "UNKNOWN")
    category = library_row.get("category", "미분류")
    peak_multi = _safe_float(library_row.get("peak_multiplier"), 1.0)
    rise_start = library_row.get("rise_start_date", "YYYY-MM-DD")
    notes = library_row.get("notes", "")

    # Ensure jsonb fields are dict/list
    pre_rise_signals = library_row.get("pre_rise_signals")
    if isinstance(pre_rise_signals, str):
        try:
            pre_rise_signals = json.loads(pre_rise_signals)
        except Exception:
            pre_rise_signals = {}
    elif pre_rise_signals is None:
        pre_rise_signals = {}

    triggers = library_row.get("triggers")
    if isinstance(triggers, str):
        try:
            triggers = json.loads(triggers)
        except Exception:
            triggers = []
    elif triggers is None:
        triggers = []

    quant = pre_rise_signals.get("quant", {})
    keywords = pre_rise_signals.get("keywords", [])
    special = pre_rise_signals.get("special", {})
    sector = pre_rise_signals.get("sector_required")
    amount_th = pre_rise_signals.get("amount_threshold_billions")
    min_kw = pre_rise_signals.get("min_keyword_matches", 1)

    # 1. 문제 재정의 (Redefine)
    redefine = {
        "user_problem": f"{ticker} 종목은 어떻게 {peak_multi:.1f}배 상승했는가?",
        "objective_problem": f"{rise_start} 상승 시작 이후 {category} 카테고리에서 {peak_multi:.1f}x 상승",
        "confirmed_facts": [
            f"rise_start_date: {rise_start}",
            f"peak_multiplier: {peak_multi:.1f}x",
        ],
        "unconfirmed_assumptions": [
            "과거 유사한 상승 패턴이 현재 종목에도 유효할 것인가"
        ]
    }
    if notes:
        redefine["confirmed_facts"].append(f"notes: {notes}")
    if quant:
        redefine["confirmed_facts"].extend([f"{k}: {v}" for k, v in quant.items()])

    # 2. Predicates
    predicates = []
    p_id_seq = 1
    
    if quant.get("bcr_at_signal"):
        predicates.append({
            "id": f"P{p_id_seq}",
            "condition": f"BCR >= {quant['bcr_at_signal']} (수주잔고/매출 배율)",
            "how_to_check": "financials.order_backlog / revenue",
            "status": "confirmed",
            "value_at_signal": quant['bcr_at_signal']
        })
        p_id_seq += 1
    if quant.get("backlog_yoy_pct"):
        predicates.append({
            "id": f"P{p_id_seq}",
            "condition": f"수주잔고 YoY >= {quant['backlog_yoy_pct']}%",
            "how_to_check": "order_backlog vs prev year",
            "status": "confirmed",
            "value_at_signal": quant['backlog_yoy_pct']
        })
        p_id_seq += 1
    if quant.get("opm_delta_at_signal") or quant.get("opm_at_signal"):
        val = quant.get("opm_delta_at_signal", quant.get("opm_at_signal", 0))
        predicates.append({
            "id": f"P{p_id_seq}",
            "condition": f"OPM 혹은 OPM 변화폭 >= {val}",
            "how_to_check": "financials.op_margin",
            "status": "confirmed",
            "value_at_signal": val
        })
        p_id_seq += 1
    if keywords:
        predicates.append({
            "id": f"P{p_id_seq}",
            "condition": f"키워드 매칭 >= {min_kw}개 ({', '.join(keywords[:3])}...)",
            "how_to_check": "filings raw_text or headline",
            "status": "confirmed"
        })
        p_id_seq += 1
    if sector:
        predicates.append({
            "id": f"P{p_id_seq}",
            "condition": f"섹터 일치 ({sector})",
            "how_to_check": "stock_data.sector_tag",
            "status": "confirmed"
        })
        p_id_seq += 1

    # 3. Producers & 4. Traces
    producers = []
    traces = []
    pr_id_seq = 1

    # Triggers를 기반으로 Producer와 Trace 매핑
    for idx, t in enumerate(triggers):
        pr_id = f"PR{pr_id_seq}"
        t_name = t.get("name", f"Trigger_{idx}")
        t_weight = _safe_float(t.get("weight"), 1.0)
        
        # Producer
        producers.append({
            "id": pr_id,
            "category": "시장/외부환경" if t_weight < 1.0 else "데이터/재무",
            "candidate": t_name,
            "related_predicates": [p["id"] for p in predicates],
            "likelihood": "high" if t_weight >= 1.0 else "medium",
            "reason": f"Timeline sequence {t.get('seq', idx)} (months_from_rise: {t.get('months_from_rise', 0)})",
            "trigger_seq": t.get("seq", idx)
        })

        # Trace
        t_sigs = t.get("signals", {})
        t_kws = t_sigs.get("keywords", [])
        trace_str = f"발화 신호 확인: {', '.join(t_kws[:3])}" if t_kws else "정량적 데이터 확인"
        traces.append({
            "producer_id": pr_id,
            "trace": trace_str,
            "where": "DART filings" if t_kws else "Financial statements",
            "importance": "high" if t_weight >= 1.0 else "medium",
            "found": True,
            "found_date": rise_start,
            "judgment": "트리거 조건 부합 → 확정"
        })
        pr_id_seq += 1

    # 특별한 이벤트가 있는 경우 Producer 추가
    if special:
        pr_id = f"PR{pr_id_seq}"
        special_k = list(special.keys())[0]
        special_v = special[special_k]
        producers.append({
            "id": pr_id,
            "category": "정책/특수이벤트",
            "candidate": f"특수 조건: {special_k} = {special_v}",
            "related_predicates": [p["id"] for p in predicates],
            "likelihood": "high",
            "reason": "pre_rise_signals.special 명시됨",
            "trigger_seq": -1
        })
        traces.append({
            "producer_id": pr_id,
            "trace": "라이브러리 기록 확인",
            "where": "Manual review / Special Event",
            "importance": "high",
            "found": True,
            "found_date": rise_start,
            "judgment": "확정"
        })
        pr_id_seq += 1

    # 5. Priority Scores
    priority_scores = []
    for pr in producers:
        w = 1.0
        # If it matches a highly weighted trigger
        for t in triggers:
            if t.get("name") == pr["candidate"]:
                w = _safe_float(t.get("weight"), 1.0)
                break
        
        # 임의의 점수 부여 로직
        score = int(w * 10)
        priority_scores.append({
            "producer_id": pr["id"],
            "relevance": min(5, max(1, int(w*2 + 2))),
            "evidence_strength": min(5, max(1, int(w*3))),
            "timing": 4,
            "repetition": 3,
            "refutation_risk": 2,
            "total": score,
            "summary": "주요 트리거" if w >= 1.0 else "배경 요인"
        })

    # 6. Resolutions (Detector Rules)
    # 현재 탐지 로직에 사용될 핵심 룰 정의
    resolutions = []
    if producers:
        # 우선순위가 가장 높은 Producer 선택
        priority_scores.sort(key=lambda x: x["total"], reverse=True)
        top_pr_id = priority_scores[0]["producer_id"]
        
        # detector_rule 작성
        detector_rule = {
            "category": category,
            "conditions": {}
        }
        
        if quant:
            for k, v in quant.items():
                detector_rule["conditions"][f"{k}"] = v
        if sector:
            detector_rule["conditions"]["sector_required"] = sector
        if keywords:
            detector_rule["conditions"]["keywords"] = keywords
            detector_rule["conditions"]["min_keyword_matches"] = min_kw
        if amount_th:
            detector_rule["conditions"]["amount_threshold_billions"] = amount_th

        resolutions.append({
            "priority": 1,
            "action": f"{category} 카테고리 {peak_multi:.1f}x 상승 패턴 감지 시 매수 검토",
            "producer_id": top_pr_id,
            "expected_effect": "상승 초기 포착 가능성",
            "risk": "거시 경제 및 개별 악재 존재 시 무효화",
            "difficulty": "낮음 (자동 탐지됨)",
            "detector_rule": detector_rule
        })

    # 7. Conclusion
    top3_traces = [t["trace"] for t in traces[:3]]
    conclusion = {
        "most_likely_cause": producers[0]["candidate"] if producers else "정보 부족",
        "why_not_confirmed_as_single": "여러 복합적 요인(정량+정성)의 결합",
        "top3_traces": top3_traces,
        "immediate_actions": [
            f"PPTR 디텍터를 이용해 {category} 종목 스크리닝"
        ],
        "actions_to_avoid": [
            "단일 트리거만 보고 성급히 판단"
        ]
    }

    pptr_json = {
        "version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "redefine": redefine,
        "predicates": predicates,
        "producers": producers,
        "traces": traces,
        "priority_scores": priority_scores,
        "resolutions": resolutions,
        "conclusion": conclusion
    }

    return pptr_json
