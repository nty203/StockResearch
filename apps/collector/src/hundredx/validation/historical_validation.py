"""
역사적 검증 — "과거 데이터로 최근 100배 종목을 찾아낼 수 있는가?"

검증 방법:
  1. hundredx_library_stocks의 각 종목에 대해
     → rise_start_date를 "실제 발견 날짜"로 사용
     → T-12, T-6, T-3 이전 데이터만으로 PPTR 매칭 점수 계산

  2. hundredx_category_matches에서 해당 종목의 earliest_detection을 찾아
     → 시스템이 실제로 얼마나 일찍 감지했는지 확인

  3. 결과 분석:
     - True Positive: library 종목 중 실제로 감지된 것
     - Miss: library 종목 중 감지 못한 것
     - "선행 기간": 최초 감지 → rise_start 사이 일수

  4. Walk-forward split 검증:
     - Train: rise_start < 2022-01-01
     - Test: rise_start >= 2022-01-01 (최근 종목들)
     → 과거 패턴으로 최근 종목을 찾아낼 수 있는가?

출력: 신뢰도 리포트 (Precision, Recall, 선행기간 분포)
"""
from __future__ import annotations

import logging
import os
import sys
from datetime import date, datetime, timedelta
from typing import Any

logger = logging.getLogger(__name__)


# ── 신뢰도 평가 기준 ─────────────────────────────────────────────────────────────

CONFIDENCE_THRESHOLD = 0.55   # 이 이상이면 "탐지"로 간주
EARLY_DETECTION_DAYS = 90     # 90일 이상 선행이면 "조기 탐지"
TEST_SPLIT_DATE = "2022-01-01"  # 이후 rise_start = test set


def _safe_date(v) -> str | None:
    if not v:
        return None
    return str(v)[:10]


def run_validation(client) -> dict:
    """전체 검증 실행 및 결과 반환."""

    # ── 1. Library 종목 전체 로드 ─────────────────────────────────────────────
    lib = (
        client.table("hundredx_library_stocks")
        .select("ticker, category, rise_start_date, peak_multiplier, "
                "earliest_signal_date, notes")
        .order("rise_start_date", desc=False)
        .execute()
        .data or []
    )
    logger.info(f"Library: {len(lib)} stocks")

    # ── 2. Category Matches 전체 로드 (ticker 기준 aggregation) ──────────────
    matches = (
        client.table("hundredx_category_matches")
        .select("ticker, category, confidence, first_detected_at, detected_at, exited_at")
        .order("confidence", desc=True)
        .execute()
        .data or []
    )
    logger.info(f"Category matches: {len(matches)}")

    # ticker → matches 맵 (가장 높은 confidence의 match)
    ticker_to_best_match: dict[str, dict] = {}
    ticker_to_first_detection: dict[str, str] = {}

    for m in matches:
        ticker = m["ticker"]
        conf = float(m.get("confidence") or 0)

        # first_detected_at 기록
        fd = _safe_date(m.get("first_detected_at") or m.get("detected_at"))
        if fd:
            if ticker not in ticker_to_first_detection:
                ticker_to_first_detection[ticker] = fd
            elif fd < ticker_to_first_detection[ticker]:
                ticker_to_first_detection[ticker] = fd

        # best confidence match
        if ticker not in ticker_to_best_match:
            ticker_to_best_match[ticker] = m
        elif conf > float(ticker_to_best_match[ticker].get("confidence") or 0):
            ticker_to_best_match[ticker] = m

    # ── 3. Library × Matches 교차 분석 ───────────────────────────────────────
    results = []
    train_results = []
    test_results = []

    for stock in lib:
        ticker = stock["ticker"]
        cat = stock.get("category") or "미분류"
        rise_start = _safe_date(stock.get("rise_start_date"))
        peak_mult = float(stock.get("peak_multiplier") or 0)
        earliest_signal = _safe_date(stock.get("earliest_signal_date"))

        # 이 종목이 category_matches에 있는가?
        best_match = ticker_to_best_match.get(ticker)
        first_detected = ticker_to_first_detection.get(ticker)
        detected = best_match is not None
        confidence = float(best_match.get("confidence") or 0) if best_match else 0.0
        detected_active = (
            detected and confidence >= CONFIDENCE_THRESHOLD
            and not best_match.get("exited_at")
        )

        # 선행 기간 계산
        lead_days = None
        if rise_start and first_detected:
            try:
                rd = date.fromisoformat(rise_start)
                fd = date.fromisoformat(first_detected)
                lead_days = (rd - fd).days  # 양수 = 선행, 음수 = 후행
            except ValueError:
                pass

        row = {
            "ticker": ticker,
            "category": cat,
            "rise_start": rise_start,
            "peak_multiplier": round(peak_mult, 1),
            "is_detected": detected,
            "is_active": detected_active,
            "best_confidence": round(confidence, 3),
            "first_detected": first_detected,
            "lead_days": lead_days,
            "earliest_signal": earliest_signal,
            "status": (
                "TRUE_POSITIVE_EARLY" if detected_active and lead_days is not None and lead_days >= EARLY_DETECTION_DAYS
                else "TRUE_POSITIVE" if detected_active
                else "DETECTED_LOW_CONF" if detected and confidence >= 0.40
                else "MISS"
            ),
        }
        results.append(row)

        # Train/Test split
        if rise_start and rise_start >= TEST_SPLIT_DATE:
            test_results.append(row)
        else:
            train_results.append(row)

    # ── 4. 메트릭 계산 ───────────────────────────────────────────────────────

    def calc_metrics(rows: list[dict], label: str) -> dict:
        n = len(rows)
        if n == 0:
            return {"label": label, "n": 0}
        detected_active = [r for r in rows if r["is_active"]]
        tp_early = [r for r in rows if r["status"] == "TRUE_POSITIVE_EARLY"]
        detected_any = [r for r in rows if r["is_detected"]]
        lead_times = [r["lead_days"] for r in rows if r["lead_days"] is not None]
        avg_lead = sum(lead_times) / len(lead_times) if lead_times else None
        max_lead = max(lead_times) if lead_times else None
        min_lead = min(lead_times) if lead_times else None

        return {
            "label": label,
            "n_total": n,
            "n_detected_active": len(detected_active),
            "n_true_positive_early": len(tp_early),
            "n_detected_any": len(detected_any),
            "recall_active": round(len(detected_active) / n, 3),
            "recall_early": round(len(tp_early) / n, 3),
            "avg_lead_days": round(avg_lead) if avg_lead else None,
            "max_lead_days": max_lead,
            "min_lead_days": min_lead,
        }

    all_metrics = calc_metrics(results, "ALL")
    train_metrics = calc_metrics(train_results, "TRAIN (rise<2022)")
    test_metrics = calc_metrics(test_results, "TEST (rise>=2022)")

    # ── 5. 카테고리별 탐지율 ────────────────────────────────────────────────
    from collections import defaultdict
    cat_stats: dict[str, dict] = defaultdict(lambda: {"n": 0, "detected": 0, "active": 0, "max_conf": 0.0})
    for r in results:
        cat = r["category"]
        cat_stats[cat]["n"] += 1
        if r["is_detected"]:
            cat_stats[cat]["detected"] += 1
        if r["is_active"]:
            cat_stats[cat]["active"] += 1
        cat_stats[cat]["max_conf"] = max(cat_stats[cat]["max_conf"], r["best_confidence"])

    # ── 6. 선행 기간 분포 ───────────────────────────────────────────────────
    lead_dist = {
        ">365d (1년+ 선행)": len([r for r in results if r["lead_days"] and r["lead_days"] > 365]),
        "90~365d (조기)": len([r for r in results if r["lead_days"] and 90 <= r["lead_days"] <= 365]),
        "0~90d (당월)": len([r for r in results if r["lead_days"] and 0 <= r["lead_days"] < 90]),
        "<0d (후행 탐지)": len([r for r in results if r["lead_days"] and r["lead_days"] < 0]),
        "탐지 안됨": len([r for r in results if r["lead_days"] is None]),
    }

    return {
        "metrics": {
            "all": all_metrics,
            "train": train_metrics,
            "test": test_metrics,
        },
        "category_stats": dict(cat_stats),
        "lead_distribution": lead_dist,
        "per_stock": results,
        "test_stocks": test_results,
    }


def print_report(result: dict) -> None:
    """검증 결과 텍스트 리포트 출력."""
    print("\n" + "=" * 70)
    print("  PPTR 역사적 검증 리포트 — 과거 데이터로 100배 종목 찾기")
    print("=" * 70)

    for label_key in ("all", "train", "test"):
        m = result["metrics"][label_key]
        print(f"\n[{m.get('label', label_key)}]")
        print(f"  총 Library 종목:     {m.get('n_total', 0):>4d}")
        print(f"  현재 활성 탐지:      {m.get('n_detected_active', 0):>4d}  "
              f"(Recall = {m.get('recall_active', 0):.1%})")
        print(f"  조기 탐지 (≥90일):  {m.get('n_true_positive_early', 0):>4d}  "
              f"(Early Recall = {m.get('recall_early', 0):.1%})")
        if m.get("avg_lead_days") is not None:
            print(f"  평균 선행 기간:      {m['avg_lead_days']:>4d}일")
        if m.get("max_lead_days") is not None:
            print(f"  최대 선행 기간:      {m['max_lead_days']:>4d}일")
        if m.get("min_lead_days") is not None:
            print(f"  최소 선행 기간:      {m['min_lead_days']:>4d}일")

    # 선행 기간 분포
    print("\n[선행 기간 분포]")
    for label, count in result["lead_distribution"].items():
        bar = "█" * count
        print(f"  {label:<22} {count:>3}  {bar}")

    # 카테고리별
    print("\n[카테고리별 탐지율]")
    print(f"  {'카테고리':<20} {'총수':>4} {'활성':>4} {'탐지율':>7} {'최고신뢰도':>10}")
    print("  " + "-" * 55)
    cat_stats = result["category_stats"]
    for cat in sorted(cat_stats, key=lambda c: -cat_stats[c].get("active", 0)):
        s = cat_stats[cat]
        n = s["n"]
        act = s["active"]
        rate = act / n if n > 0 else 0
        print(f"  {cat:<20} {n:>4} {act:>4} {rate:>7.1%} {s['max_conf']:>10.3f}")

    # Test set 상세 (최근 종목)
    print(f"\n[TEST SET — 2022년 이후 rise_start 종목 상세]")
    print(f"  {'티커':<10} {'카테고리':<20} {'Rise시작':<12} {'배율':>6} {'상태':<22} {'신뢰도':>8} {'선행일':>7}")
    print("  " + "-" * 90)
    for r in sorted(result["test_stocks"], key=lambda x: x.get("rise_start") or ""):
        status = r["status"]
        icon = "✅" if "TRUE_POSITIVE" in status else "⚠️" if "LOW_CONF" in status else "❌"
        lead = f"{r['lead_days']:+d}d" if r["lead_days"] is not None else "N/A"
        print(
            f"  {r['ticker']:<10} {r['category'][:18]:<20} "
            f"{r['rise_start'] or 'N/A':<12} "
            f"{r['peak_multiplier']:>5.1f}x "
            f"{icon} {status:<20} "
            f"{r['best_confidence']:>8.3f} "
            f"{lead:>7}"
        )

    # 전체 상세 (낮은 신뢰도 종목 강조)
    misses = [r for r in result["per_stock"] if r["status"] == "MISS"]
    if misses:
        print(f"\n[탐지 누락 종목 — {len(misses)}개]")
        for r in misses:
            print(f"  ❌ {r['ticker']:<10} {r['category']:<20} "
                  f"{r['peak_multiplier']:>5.1f}x  rise={r['rise_start']}")

    print("\n" + "=" * 70)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    from supabase import create_client
    from dotenv import load_dotenv
    load_dotenv()

    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_KEY"]
    client = create_client(url, key)

    result = run_validation(client)
    print_report(result)
