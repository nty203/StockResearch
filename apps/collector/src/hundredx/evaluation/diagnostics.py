"""평가 A — Diagnostics: 현재 match 분포 / 결측 / 미스매치 즉시 측정.

scanner 결과의 입력 데이터 품질과 분류 균형도를 측정한다. 시점 여행 불필요.

핵심 지표:
  - category_distribution / entropy   : 카테고리 쏠림 탐지
  - body_coverage_pct                 : 검증 가능성 (공시 본문 결측률)
  - llm_verdict_distribution          : confirm/uncertain/reject 비율
  - library_overlap_rate              : 신규 후보 vs 라이브러리 재탐지 비율
  - confidence_stats_per_verdict      : LLM 판정별 confidence 분포 (calibration 사전 신호)
"""
from __future__ import annotations

import math
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from statistics import mean, median

from ._db import fetch_all


def _percentile(values: list[float], p: float) -> float | None:
    if not values:
        return None
    s = sorted(values)
    k = (len(s) - 1) * p
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return s[int(k)]
    return s[f] + (s[c] - s[f]) * (k - f)


def _extract_llm_verdict(evidence: list) -> str | None:
    """evidence 배열에서 가장 최근 llm_verdict entry 추출.

    _llm_apply_verdicts.py 는 verdict 키 없이 text_excerpt="LLM confirm: ..." 형태로 저장.
    explicit verdict 키도 함께 지원 (forward compat).
    """
    if not evidence:
        return None
    llm = [e for e in evidence if isinstance(e, dict) and e.get("source_type") == "llm_verdict"]
    if not llm:
        return None
    last = llm[-1]
    if last.get("verdict"):
        return str(last["verdict"]).lower()
    excerpt = str(last.get("text_excerpt") or "").lower()
    for v in ("confirm", "reject", "uncertain"):
        if f"llm {v}" in excerpt or excerpt.startswith(v):
            return v
    return None


def _body_present(evidence: list) -> bool:
    """공시 본문 또는 text_excerpt 가 evidence에 들어있는지 — 검증 가능 여부."""
    if not evidence:
        return False
    for e in evidence:
        if not isinstance(e, dict):
            continue
        body = e.get("body") or e.get("raw_text") or e.get("text_excerpt")
        if body and len(str(body)) > 20:
            return True
    return False


def compute_diagnostics(client, window_days: int = 90) -> dict:
    """최근 window_days 내 first_detected_at 매치를 평가."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=window_days)).isoformat()
    matches = fetch_all(lambda s, e: (
        client.table("hundredx_category_matches")
        .select("ticker, category, confidence, evidence, first_detected_at, exited_at")
        .gte("first_detected_at", cutoff)
        .range(s, e)
    ))

    # library tickers — for overlap rate
    lib_rows = fetch_all(lambda s, e: (
        client.table("hundredx_library_stocks").select("ticker").range(s, e)
    ))
    lib_tickers = {r["ticker"] for r in lib_rows}

    # ── A.1 카테고리 분포 + entropy ────────────────────────────────────────────
    cat_count: dict[str, int] = defaultdict(int)
    for m in matches:
        cat_count[m["category"]] += 1
    total = len(matches) or 1
    probs = [n / total for n in cat_count.values()]
    entropy = -sum(p * math.log2(p) for p in probs if p > 0) if probs else 0.0
    max_entropy = math.log2(len(cat_count)) if len(cat_count) > 1 else 1.0
    entropy_ratio = entropy / max_entropy if max_entropy > 0 else 0.0

    # ── A.2 LLM verdict 분포 ──────────────────────────────────────────────────
    verdict_count: dict[str, int] = defaultdict(int)
    confidence_by_verdict: dict[str, list[float]] = defaultdict(list)
    body_present_count = 0

    for m in matches:
        evid = m.get("evidence") or []
        verdict = _extract_llm_verdict(evid) or "unverified"
        verdict_count[verdict] += 1
        conf = float(m.get("confidence") or 0)
        confidence_by_verdict[verdict].append(conf)
        if _body_present(evid):
            body_present_count += 1

    conf_stats_per_verdict = {}
    for v, confs in confidence_by_verdict.items():
        if not confs:
            continue
        conf_stats_per_verdict[v] = {
            "n": len(confs),
            "mean": round(mean(confs), 3),
            "p25": round(_percentile(confs, 0.25) or 0, 3),
            "p50": round(median(confs), 3),
            "p75": round(_percentile(confs, 0.75) or 0, 3),
        }

    # ── A.3 라이브러리 overlap (신규 후보 vs 라이브러리 종목 재탐지) ──────────
    lib_overlap = sum(1 for m in matches if m["ticker"] in lib_tickers)
    overlap_rate = lib_overlap / total if total else 0.0

    # ── A.4 카테고리별 verdict breakdown ──────────────────────────────────────
    cat_verdict: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for m in matches:
        evid = m.get("evidence") or []
        v = _extract_llm_verdict(evid) or "unverified"
        cat_verdict[m["category"]][v] += 1

    # ── A.5 결측 매치 (filings/evidence 없음) ─────────────────────────────────
    empty_evidence = sum(1 for m in matches if not (m.get("evidence") or []))

    return {
        "n_matches": total,
        "window_days": window_days,
        "category_distribution": dict(cat_count),
        "category_entropy_bits": round(entropy, 3),
        "category_entropy_ratio": round(entropy_ratio, 3),
        "body_coverage_pct": round(100.0 * body_present_count / total, 1) if total else 0.0,
        "empty_evidence_count": empty_evidence,
        "llm_verdict_distribution": dict(verdict_count),
        "confidence_stats_per_verdict": conf_stats_per_verdict,
        "library_overlap_rate": round(overlap_rate, 3),
        "library_overlap_count": lib_overlap,
        "category_verdict_breakdown": {k: dict(v) for k, v in cat_verdict.items()},
    }
