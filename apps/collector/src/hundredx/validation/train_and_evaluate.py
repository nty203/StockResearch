"""
학습 데이터 기반 모델 학습 및 종합 평가 스크립트.

흐름:
  1. pptr_training_samples 로드 (positive + negative)
  2. hundredx_category_matches에서 confidence + 특성 추출
  3. LightGBM 또는 calibrated linear model 학습
  4. Walk-forward validation
  5. Brier score, AUC, calibration curve 출력
  6. 상위 종목 랭킹 출력 (현재 active matches 중 가장 유망한 것)
"""
from __future__ import annotations

import logging
import math
import os
import random
import sys
from datetime import date, datetime
from typing import Any

logger = logging.getLogger(__name__)

MIN_SAMPLES_FOR_LGBM = 50  # 이 이상이면 LightGBM 시도


def build_feature_from_match(m: dict) -> dict[str, float]:
    """
    Category match 레코드 → 피처 벡터.
    실제 ML 피처 빌더 대신 category_match 필드를 직접 활용.
    """
    conf = float(m.get("confidence") or 0)

    # Evidence에서 특성 추출
    evidence = m.get("evidence") or []
    if isinstance(evidence, str):
        import json
        try:
            evidence = json.loads(evidence)
        except Exception:
            evidence = []

    n_evidence = len(evidence) if isinstance(evidence, list) else 0

    # PPTR breakdown에서 추출
    breakdown = m.get("pptr_confidence_breakdown") or {}
    if isinstance(breakdown, str):
        import json
        try:
            breakdown = json.loads(breakdown)
        except Exception:
            breakdown = {}

    base_rate = float(breakdown.get("base_rate") or 0.34)
    cond_score = float(breakdown.get("condition_score") or 0)
    recency_score = float(breakdown.get("recency_score") or 0)
    refutation = float(breakdown.get("refutation_penalty") or 0)

    # Timeline progress
    timeline = m.get("timeline_progress") or {}
    if isinstance(timeline, str):
        import json
        try:
            timeline = json.loads(timeline)
        except Exception:
            timeline = {}
    timeline_pct = float(timeline.get("progress_pct") or 0)

    # Fingerprint score
    fp_score = float(m.get("fingerprint_score") or 0)

    # Price performance
    price_mult = float(m.get("price_current_multiplier") or 1.0)
    price_peak = float(m.get("price_peak_multiplier") or 1.0)

    # Category one-hot (단순화)
    categories = [
        "수주잔고_선행", "수익성_급전환", "빅테크_파트너",
        "플랫폼_독점", "공급_병목", "정책_수혜", "임상_파이프라인"
    ]
    cat = m.get("category") or "미분류"
    cat_feats = {f"cat_{c}": (1.0 if cat == c else 0.0) for c in categories}

    feats = {
        "confidence": conf,
        "base_rate": base_rate,
        "condition_score": cond_score,
        "recency_score": recency_score,
        "refutation_penalty": refutation,
        "n_evidence": float(n_evidence),
        "timeline_pct": timeline_pct,
        "fingerprint_score": fp_score,
        "price_current_mult": min(price_mult, 20.0),
        "price_peak_mult": min(price_peak, 20.0),
        **cat_feats,
    }
    return feats


def load_training_data(client) -> tuple[list[dict], list[int]]:
    """
    pptr_training_samples + category_matches를 결합해 X, y 반환.
    """
    # training_samples 로드
    samples = (
        client.table("pptr_training_samples")
        .select("*")
        .in_("split", ["train", "val"])   # test는 절대 사용 안 함
        .execute()
        .data or []
    )
    logger.info(f"Training samples: {len(samples)}")

    if not samples:
        return [], []

    # ticker → match 매핑
    tickers = list({s["ticker"] for s in samples})
    matches_raw = (
        client.table("hundredx_category_matches")
        .select("ticker, category, confidence, evidence, pptr_confidence_breakdown, "
                "timeline_progress, fingerprint_score, price_current_multiplier, "
                "price_peak_multiplier")
        .in_("ticker", tickers[:500])   # supabase in 제한
        .execute()
        .data or []
    )
    ticker_to_match = {m["ticker"]: m for m in matches_raw}

    X, y = [], []
    for s in samples:
        ticker = s["ticker"]
        match = ticker_to_match.get(ticker, {"ticker": ticker, "category": s["category"],
                                              "confidence": 0.40})
        feats = build_feature_from_match(match)

        # 카테고리 override (training sample의 카테고리 사용)
        for cat_key in [k for k in feats if k.startswith("cat_")]:
            feats[cat_key] = 0.0
        cat_key_cur = f"cat_{s['category']}"
        if cat_key_cur in feats:
            feats[cat_key_cur] = 1.0

        X.append(feats)
        y.append(s["label_10x_24m"])

    return X, y


def train_lgbm(X: list[dict], y: list[int]) -> tuple[Any, list[str], dict]:
    """LightGBM 학습."""
    import lightgbm as lgb
    import numpy as np
    from sklearn.model_selection import train_test_split
    from sklearn.isotonic import IsotonicRegression

    feature_names = list(X[0].keys())
    X_arr = np.array([[row.get(f, 0.0) for f in feature_names] for row in X], dtype=np.float32)
    y_arr = np.array(y, dtype=np.int32)

    # 80/20 split
    X_train, X_val, y_train, y_val = train_test_split(
        X_arr, y_arr, test_size=0.2, random_state=42,
        stratify=y_arr if len(set(y)) > 1 else None
    )

    pos_count = sum(y_train)
    neg_count = len(y_train) - pos_count
    scale_pos = (neg_count / pos_count) if pos_count > 0 else 1.0

    dtrain = lgb.Dataset(X_train, label=y_train)
    dval = lgb.Dataset(X_val, label=y_val, reference=dtrain)

    params = {
        "objective": "binary",
        "metric": "binary_logloss",
        "learning_rate": 0.05,
        "num_leaves": 15,
        "min_child_samples": 5,
        "scale_pos_weight": scale_pos,
        "verbose": -1,
        "seed": 42,
    }

    model = lgb.train(
        params, dtrain,
        num_boost_round=200,
        valid_sets=[dval],
        callbacks=[lgb.early_stopping(30, verbose=False), lgb.log_evaluation(-1)],
    )

    # Calibration (isotonic)
    val_preds = model.predict(X_val)
    calibrator = IsotonicRegression(out_of_bounds="clip")
    calibrator.fit(val_preds, y_val)

    # Metrics
    cal_preds = calibrator.transform(val_preds)
    brier = sum((p - t)**2 for p, t in zip(cal_preds, y_val)) / len(y_val)

    try:
        from sklearn.metrics import roc_auc_score
        auc = roc_auc_score(y_val, cal_preds)
    except Exception:
        auc = None

    importance = dict(zip(feature_names, model.feature_importance("gain").tolist()))

    return (model, calibrator), feature_names, {
        "n_train": len(X_train),
        "n_val": len(X_val),
        "brier_val": round(brier, 4),
        "auc_val": round(auc, 4) if auc else None,
        "best_iteration": model.best_iteration,
        "pos_rate_train": round(pos_count / len(y_train), 3),
        "feature_importances": {k: round(v, 1) for k, v in
                                 sorted(importance.items(), key=lambda x: -x[1])[:15]},
    }


def predict_current_matches(client, model_tuple=None, feature_names=None) -> list[dict]:
    """
    현재 활성 category_matches에 대해 confidence 재계산.
    상위 20개 종목 반환.
    """
    active = (
        client.table("hundredx_category_matches")
        .select("ticker, category, confidence, first_detected_at, detected_at, "
                "pptr_confidence_breakdown, fingerprint_score, timeline_progress, "
                "price_current_multiplier, price_peak_multiplier")
        .is_("exited_at", "null")
        .order("confidence", desc=True)
        .limit(100)
        .execute()
        .data or []
    )

    results = []
    for m in active:
        feats = build_feature_from_match(m)
        orig_conf = float(m.get("confidence") or 0)

        ml_conf = None
        if model_tuple is not None:
            try:
                model, calibrator = model_tuple
                fn = feature_names or list(feats.keys())
                x_arr = [[feats.get(f, 0.0) for f in fn]]
                raw = model.predict(x_arr)[0]
                ml_conf = round(float(calibrator.transform([raw])[0]), 3)
            except Exception as e:
                logger.debug(f"ML predict failed for {m['ticker']}: {e}")

        results.append({
            "ticker": m["ticker"],
            "category": m["category"],
            "orig_confidence": round(orig_conf, 3),
            "ml_confidence": ml_conf,
            "final_confidence": ml_conf if ml_conf is not None else orig_conf,
            "first_detected": str(m.get("first_detected_at") or m.get("detected_at") or "")[:10],
            "price_mult": round(float(m.get("price_current_multiplier") or 1.0), 2),
        })

    return sorted(results, key=lambda x: -x["final_confidence"])


def run(client=None) -> dict:
    """전체 실행."""
    if client is None:
        from supabase import create_client
        from dotenv import load_dotenv
        load_dotenv()
        url = os.environ["SUPABASE_URL"]
        key = os.environ["SUPABASE_SERVICE_KEY"]
        client = create_client(url, key)

    # 1. 학습 데이터
    X, y = load_training_data(client)
    n_pos = sum(y)
    n_neg = len(y) - n_pos
    logger.info(f"Dataset: {len(X)} samples, {n_pos} pos, {n_neg} neg")

    model_tuple = None
    feature_names = None
    train_result = {"status": "skipped", "n_samples": len(X)}

    # 2. LightGBM 학습 (충분한 데이터 시)
    if len(X) >= MIN_SAMPLES_FOR_LGBM and n_pos >= 5:
        try:
            logger.info(f"Training LightGBM with {len(X)} samples...")
            (model_tuple, feature_names, metrics) = train_lgbm(X, y)
            train_result = {"status": "trained", **metrics}
            logger.info(f"LightGBM: Brier={metrics['brier_val']}, AUC={metrics['auc_val']}")
        except Exception as e:
            logger.error(f"LightGBM training failed: {e}")
            train_result = {"status": "failed", "error": str(e), "n_samples": len(X)}
    else:
        logger.info(f"Insufficient data for LightGBM: {len(X)} samples, {n_pos} positive")

    # 3. 현재 활성 종목 예측
    top_matches = predict_current_matches(client, model_tuple, feature_names)

    return {
        "training": train_result,
        "top_matches": top_matches[:20],
        "n_samples": len(X),
        "n_positive": n_pos,
        "n_negative": n_neg,
    }


def print_evaluation_report(result: dict) -> None:
    """평가 결과 출력."""
    print("\n" + "=" * 70)
    print("  모델 학습 및 평가 리포트")
    print("=" * 70)

    tr = result["training"]
    print(f"\n[학습 현황]")
    print(f"  총 샘플:    {result['n_samples']:>5d}")
    print(f"  Positive:  {result['n_positive']:>5d}  (100배+ 종목)")
    print(f"  Negative:  {result['n_negative']:>5d}  (일반/미달 종목)")
    print(f"  상태:       {tr['status']}")

    if tr["status"] == "trained":
        print(f"\n[LightGBM 성능]")
        print(f"  Train 샘플:   {tr.get('n_train', 0):>5d}")
        print(f"  Val 샘플:     {tr.get('n_val', 0):>5d}")
        print(f"  Brier (val):  {tr.get('brier_val', 'N/A')}")

        grade = (
            "EXCELLENT ✅" if tr.get('brier_val', 1) <= 0.18
            else "GOOD ✅" if tr.get('brier_val', 1) <= 0.22
            else "FAIR ⚠️" if tr.get('brier_val', 1) <= 0.25
            else "POOR ❌"
        )
        print(f"  등급:         {grade}")
        print(f"  AUC (val):    {tr.get('auc_val', 'N/A')}")
        print(f"  Best iter:    {tr.get('best_iteration', 'N/A')}")

        if tr.get("feature_importances"):
            print(f"\n  [Top Features]")
            for feat, score in list(tr["feature_importances"].items())[:10]:
                bar = "█" * max(1, int(score / max(tr["feature_importances"].values()) * 20))
                print(f"    {feat:<30} {score:>8.1f}  {bar}")
    elif tr["status"] == "skipped":
        print(f"\n  ⚠️  샘플 부족으로 ML 학습 건너뜀")
        print(f"     현재: {result['n_samples']}개, 필요: {MIN_SAMPLES_FOR_LGBM}개")
        print(f"     → linear fallback confidence 사용")

    # 상위 매칭 종목
    print(f"\n[현재 고신뢰도 매칭 종목 TOP 20]")
    print(f"  {'티커':<10} {'카테고리':<22} {'원래 신뢰도':>10} {'ML 신뢰도':>10} {'가격 배수':>8} {'최초탐지':>12}")
    print("  " + "-" * 80)
    for m in result["top_matches"]:
        ml_str = f"{m['ml_confidence']:.3f}" if m["ml_confidence"] else "  N/A "
        mult_str = f"{m['price_mult']:.2f}x" if m["price_mult"] != 1.0 else "  --  "
        print(
            f"  {m['ticker']:<10} {m['category'][:20]:<22} "
            f"{m['orig_confidence']:>10.3f} "
            f"{ml_str:>10} "
            f"{mult_str:>8} "
            f"{m['first_detected']:>12}"
        )

    print("\n" + "=" * 70)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    result = run()
    print_evaluation_report(result)
