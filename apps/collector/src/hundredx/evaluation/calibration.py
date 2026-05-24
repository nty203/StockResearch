"""평가 C — Calibration: confidence가 LLM verdict(confirm 확률)를 예측하는가.

이상적으로는 confidence=0.8 인 매치의 ~80%가 confirm 이어야 함.
현실: confirm rate가 confidence와 무관하면 calibration이 깨진 것.

지표:
  - calibration_buckets : confidence 구간별 실제 confirm rate
  - brier_score         : confidence를 confirm 확률로 사용한 평균 제곱 오차
  - spearman_corr       : confidence와 confirm 여부의 순위 상관
  - ece                 : Expected Calibration Error
"""
from __future__ import annotations

from collections import defaultdict

from ._db import fetch_all


def _extract_llm_verdict(evidence: list) -> str | None:
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


def _spearman(xs: list[float], ys: list[float]) -> float | None:
    """간이 Spearman rank correlation. scipy 없이."""
    n = len(xs)
    if n < 3 or len(ys) != n:
        return None

    def _rank(vals):
        sorted_idx = sorted(range(n), key=lambda i: vals[i])
        ranks = [0.0] * n
        i = 0
        while i < n:
            j = i
            while j + 1 < n and vals[sorted_idx[j + 1]] == vals[sorted_idx[i]]:
                j += 1
            avg_rank = (i + j) / 2 + 1
            for k in range(i, j + 1):
                ranks[sorted_idx[k]] = avg_rank
            i = j + 1
        return ranks

    rx = _rank(xs)
    ry = _rank(ys)
    mean_x = sum(rx) / n
    mean_y = sum(ry) / n
    cov = sum((rx[i] - mean_x) * (ry[i] - mean_y) for i in range(n))
    var_x = sum((r - mean_x) ** 2 for r in rx)
    var_y = sum((r - mean_y) ** 2 for r in ry)
    denom = (var_x * var_y) ** 0.5
    if denom == 0:
        return None
    return cov / denom


def compute_calibration(client, window_days: int = 365) -> dict:
    """confidence vs LLM verdict 캘리브레이션 분석.

    LLM verdict 가 있는 매치만 대상으로 분석한다.
    confirm = 1, reject = 0, uncertain = 0.5 로 매핑.
    """
    from datetime import datetime, timedelta, timezone
    cutoff = (datetime.now(timezone.utc) - timedelta(days=window_days)).isoformat()
    matches = fetch_all(lambda s, e: (
        client.table("hundredx_category_matches")
        .select("ticker, category, confidence, evidence, first_detected_at")
        .gte("first_detected_at", cutoff)
        .range(s, e)
    ))

    labeled = []  # (confidence, verdict_score)
    verdict_counts = defaultdict(int)

    for m in matches:
        v = _extract_llm_verdict(m.get("evidence") or [])
        if v is None:
            continue
        verdict_counts[v] += 1
        if v == "confirm":
            score = 1.0
        elif v == "reject":
            score = 0.0
        elif v == "uncertain":
            score = 0.5
        else:
            continue
        labeled.append((float(m.get("confidence") or 0), score))

    if not labeled:
        return {
            "n_labeled": 0,
            "note": "LLM verdict이 기록된 매치 없음 — /verify-stocks 실행 필요",
        }

    # Calibration buckets (0.05 단위)
    buckets: dict[str, list[float]] = defaultdict(list)
    for conf, score in labeled:
        b_lo = round(conf // 0.05 * 0.05, 2)
        b_key = f"{b_lo:.2f}-{b_lo + 0.05:.2f}"
        buckets[b_key].append(score)

    cal_buckets = []
    ece_terms = []
    total = len(labeled)
    for k in sorted(buckets.keys()):
        vals = buckets[k]
        bin_mean = sum(vals) / len(vals)
        bin_lo = float(k.split("-")[0])
        bin_hi = float(k.split("-")[1])
        bin_mid_conf = (bin_lo + bin_hi) / 2
        cal_buckets.append({
            "bin": k,
            "n": len(vals),
            "actual_confirm_score_mean": round(bin_mean, 3),
            "expected_confirm_score": round(bin_mid_conf, 3),
            "gap": round(bin_mean - bin_mid_conf, 3),
        })
        ece_terms.append((len(vals) / total) * abs(bin_mean - bin_mid_conf))

    ece = sum(ece_terms)
    brier = sum((c - s) ** 2 for c, s in labeled) / total
    spearman = _spearman([c for c, _ in labeled], [s for _, s in labeled])

    return {
        "n_labeled": total,
        "verdict_distribution": dict(verdict_counts),
        "brier_score": round(brier, 4),
        "expected_calibration_error": round(ece, 4),
        "spearman_corr_conf_vs_confirm": round(spearman, 4) if spearman is not None else None,
        "calibration_buckets": cal_buckets,
        "interpretation": {
            "ece_lt_0.05": "well-calibrated",
            "ece_0.05_to_0.15": "moderate miscalibration",
            "ece_gt_0.15": "severe miscalibration",
        },
    }
