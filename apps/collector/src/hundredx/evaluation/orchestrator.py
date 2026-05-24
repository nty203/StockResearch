"""평가 orchestrator — 5개 평가 모듈을 모두 실행하고 결과를 DB에 저장.

run_full_evaluation():
  1. diagnostics      (즉시, scanner 변경 불필요)
  2. forward_returns  (prices_daily 조회 — 종목 수에 비례한 시간)
  3. calibration      (즉시)
  4. library_recall   (point-in-time replay — 가장 시간 소요)
  5. summary 합성     (top-line KPI + 이슈 자동 도출)
  6. hundredx_evaluation_runs 에 1 row insert

run_kind 옵션:
  - full          : 4축 모두
  - diagnostics   : A만 (빠름)
  - calibration   : C만
  - forward_returns: B만
  - recall        : D만 (가장 느림)
"""
from __future__ import annotations

import logging
import os
import subprocess
from datetime import datetime, timezone

from ...upsert import get_client
from .diagnostics import compute_diagnostics
from .forward_returns import compute_forward_returns
from .calibration import compute_calibration
from .library_recall import compute_library_recall

logger = logging.getLogger(__name__)


def _git_commit() -> str | None:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            stderr=subprocess.DEVNULL,
            timeout=5,
        )
        return out.decode().strip()
    except Exception:
        return None


def _synth_summary(diagnostics: dict, forward_returns: dict, calibration: dict, library_recall: dict) -> dict:
    """5축 결과를 합성해 top-line KPI 와 자동 이슈 도출."""
    issues: list[str] = []
    health = "green"

    # ── 진단 기반 이슈 자동 도출 ───────────────────────────────────────────
    cat_dist = (diagnostics or {}).get("category_distribution", {})
    total_matches = sum(cat_dist.values()) if cat_dist else 0
    if total_matches > 0:
        max_cat = max(cat_dist, key=cat_dist.get)
        max_share = cat_dist[max_cat] / total_matches
        if max_share > 0.5:
            issues.append(f"카테고리 쏠림: {max_cat}가 {max_share:.0%} 차지")
            health = "yellow"

    body_cov = (diagnostics or {}).get("body_coverage_pct", 0)
    if body_cov < 50:
        issues.append(f"공시 본문 결측률 {100 - body_cov:.0f}% — 검증 불가 매치 다수")
        health = "yellow"

    cat_verdict = (diagnostics or {}).get("category_verdict_breakdown", {})
    for cat, vd in cat_verdict.items():
        # confirm率은 LLM이 실제로 평가한 매치 한정 — unverified 다수 때문에 분모 과대평가 방지
        labeled = sum(n for k, n in vd.items() if k in ("confirm", "reject", "uncertain"))
        if labeled < 5:
            continue
        confirm = vd.get("confirm", 0)
        if confirm / labeled < 0.1:
            issues.append(f"{cat}: labeled에서 confirm率 {confirm}/{labeled} — detector 정확도 낮음")
            health = "red"

    # ── Calibration 이슈 ──────────────────────────────────────────────────
    ece = (calibration or {}).get("expected_calibration_error")
    if ece is not None and ece > 0.15:
        issues.append(f"Confidence calibration 손상 (ECE={ece:.3f})")
        if health == "green":
            health = "yellow"

    spear = (calibration or {}).get("spearman_corr_conf_vs_confirm")
    if spear is not None and abs(spear) < 0.1:
        issues.append("Confidence가 verdict를 예측하지 못함 (Spearman ≈ 0)")
        if health == "green":
            health = "yellow"

    # ── Recall 이슈 ───────────────────────────────────────────────────────
    recall_buckets = (library_recall or {}).get("by_lookback") or []
    key_metrics = {}
    for b in recall_buckets:
        if b.get("lookback_days") == 90 and b.get("recall") is not None:
            key_metrics["recall_90d"] = b["recall"]
            if b["recall"] < 0.3:
                issues.append(f"라이브러리 90일 사전 recall {b['recall']:.0%} — 조기 탐지력 부족")
                health = "red"
        if b.get("lookback_days") == 365:
            key_metrics["recall_365d"] = b.get("recall")

    # Confirm precision (forward returns로 검증, 향후 365d 평균 수익률)
    fr_by_verdict = (forward_returns or {}).get("by_verdict", {})
    confirm_365 = fr_by_verdict.get("confirm", {}).get("365d", {})
    if confirm_365.get("n", 0) > 0:
        key_metrics["confirm_365d_mean_return_pct"] = confirm_365.get("mean_pct")

    reject_365 = fr_by_verdict.get("reject", {}).get("365d", {})
    if reject_365.get("n", 0) > 0:
        key_metrics["reject_365d_mean_return_pct"] = reject_365.get("mean_pct")
        if (
            confirm_365.get("n", 0) > 0
            and reject_365.get("mean_pct") is not None
            and confirm_365.get("mean_pct") is not None
            and reject_365["mean_pct"] >= confirm_365["mean_pct"]
        ):
            issues.append("Reject가 Confirm보다 365d 수익률 ↑ — LLM 판정 신뢰성 의심")
            health = "red"

    return {
        "overall_health": health,
        "issues": issues,
        "key_metrics": key_metrics,
        "n_matches_window": total_matches,
    }


def run_full_evaluation(
    run_kind: str = "full",
    window_days: int = 90,
    recall_max_stocks: int | None = None,
    recall_exclude_categories: set[str] | None = None,
    recall_category_thresholds: dict[str, float] | None = None,
    persist: bool = True,
    notes: str | None = None,
) -> dict:
    """5축 평가를 모두 실행하고 hundredx_evaluation_runs에 저장.

    Args:
        run_kind: full | diagnostics | calibration | forward_returns | recall
        window_days: diagnostics 평가 윈도우
        recall_max_stocks: library_recall 시 평가할 종목 수 제한 (개발/디버그용)
        persist: True면 DB에 저장
    """
    client = get_client()
    now = datetime.now(timezone.utc)
    logger.info("Evaluation run kind=%s window=%dd", run_kind, window_days)

    diagnostics_res = None
    forward_returns_res = None
    calibration_res = None
    library_recall_res = None

    if run_kind in ("full", "diagnostics"):
        logger.info("→ diagnostics")
        diagnostics_res = compute_diagnostics(client, window_days=window_days)

    if run_kind in ("full", "forward_returns"):
        logger.info("→ forward_returns")
        forward_returns_res = compute_forward_returns(client, window_days=730)

    if run_kind in ("full", "calibration"):
        logger.info("→ calibration")
        calibration_res = compute_calibration(client, window_days=365)

    if run_kind in ("full", "recall"):
        logger.info("→ library_recall (slow)")
        library_recall_res = compute_library_recall(
            client,
            max_stocks=recall_max_stocks,
            exclude_categories=recall_exclude_categories,
            category_thresholds=recall_category_thresholds,
        )

    summary = _synth_summary(
        diagnostics_res or {},
        forward_returns_res or {},
        calibration_res or {},
        library_recall_res or {},
    )

    n_lib = (library_recall_res or {}).get("n_library_stocks")
    n_matches = (diagnostics_res or {}).get("n_matches")

    payload = {
        "run_at": now.isoformat(),
        "run_kind": run_kind,
        "git_commit": _git_commit(),
        "params": {
            "window_days": window_days,
            "recall_max_stocks": recall_max_stocks,
            "recall_exclude_categories": sorted(recall_exclude_categories) if recall_exclude_categories else [],
            "recall_category_thresholds": recall_category_thresholds or {},
        },
        "n_matches_window": n_matches,
        "window_days": window_days,
        "n_library_stocks": n_lib,
        "diagnostics": diagnostics_res,
        "forward_returns": forward_returns_res,
        "calibration": calibration_res,
        "library_recall": library_recall_res,
        "summary": summary,
        "notes": notes,
    }

    if persist:
        try:
            insert_res = (
                client.table("hundredx_evaluation_runs")
                .insert(payload)
                .execute()
            )
            if insert_res.data:
                payload["id"] = insert_res.data[0].get("id")
                logger.info("Persisted evaluation run id=%s", payload["id"])
        except Exception as exc:
            logger.error("Failed to persist evaluation run: %s", exc)

    return payload


def main() -> None:
    import argparse
    import json
    import sys

    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    try:
        from dotenv import load_dotenv
        load_dotenv()
    except Exception:
        pass

    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    p = argparse.ArgumentParser(description="HundredX evaluation infrastructure")
    p.add_argument("--kind", default="full",
                   choices=["full", "diagnostics", "calibration", "forward_returns", "recall"])
    p.add_argument("--window-days", type=int, default=90)
    p.add_argument("--recall-max-stocks", type=int, default=None,
                   help="library_recall 평가 종목 수 제한 (디버그용)")
    p.add_argument("--exclude-categories", default=None,
                   help="recall 시 비활성화할 카테고리 (콤마 구분, 예: '수익성_급전환,단기_테마_급등')")
    p.add_argument("--category-thresholds", default=None,
                   help="카테고리별 min_confidence 차등 (예: '수익성_급전환=0.85,임상_파이프라인=0.6')")
    p.add_argument("--no-persist", action="store_true", help="DB 저장 건너뛰기")
    p.add_argument("--notes", default=None)
    p.add_argument("--print-json", action="store_true")
    args = p.parse_args()

    exclude = None
    if args.exclude_categories:
        exclude = {c.strip() for c in args.exclude_categories.split(",") if c.strip()}

    cat_thresh = None
    if args.category_thresholds:
        cat_thresh = {}
        for spec in args.category_thresholds.split(","):
            if "=" in spec:
                k, v = spec.split("=", 1)
                cat_thresh[k.strip()] = float(v.strip())

    result = run_full_evaluation(
        run_kind=args.kind,
        window_days=args.window_days,
        recall_max_stocks=args.recall_max_stocks,
        recall_exclude_categories=exclude,
        recall_category_thresholds=cat_thresh,
        persist=not args.no_persist,
        notes=args.notes,
    )

    if args.print_json:
        print(json.dumps(result, indent=2, default=str, ensure_ascii=False))
    else:
        s = result.get("summary") or {}
        print("─" * 60)
        print(f"Evaluation run: kind={result['run_kind']}  health={s.get('overall_health')}")
        print(f"  n_matches_window: {result.get('n_matches_window')}")
        print(f"  n_library_stocks: {result.get('n_library_stocks')}")
        print(f"  key_metrics: {s.get('key_metrics')}")
        if s.get("issues"):
            print("\n  Issues:")
            for issue in s["issues"]:
                print(f"    - {issue}")
        print("─" * 60)


if __name__ == "__main__":
    main()
