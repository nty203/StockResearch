"""실제 100배+ 상승 종목 사전 탐지 검증 (Point-in-time validation)

snapshot_date 시점의 실제 가격·재무 데이터로 filters_kr을 돌려
"이 종목이 상승하기 전 우리 시스템이 잡아냈을까?"를 수치로 확인한다.

사용법:
  uv run python -m src.screening.validate_100x
  uv run python -m src.screening.validate_100x --no-dart   # DART API 없이 가격만
  uv run python -m src.screening.validate_100x --save      # Supabase에 결과 저장

검증 대상:
  에코프로   086520  snapshot 2020-01-02, 실제 ~107x (2023-07-26 고점 기준)
  에코프로비엠 247540  snapshot 2020-01-02, 실제 ~22x
  엘앤에프   066970  snapshot 2020-01-02, 실제 ~16x
  한미반도체  042700  snapshot 2021-01-04, 실제 ~19x
  알테오젠   196170  snapshot 2020-01-02, 실제 ~50x
  효성중공업  298040  snapshot 2022-01-03, 실제 ~18x  ← 리포트 언급 종목

대조군 (상승 실패/소폭 상승):
  LG이노텍   011070  snapshot 2020-01-02, 실제 ~2.5x
  삼성전기   009150  snapshot 2020-01-02, 실제 ~1.8x
  SK하이닉스  000660  snapshot 2020-01-02, 실제 ~3.5x
"""
from __future__ import annotations
import logging
import os
import time
from datetime import date, timedelta

import FinanceDataReader as fdr

logger = logging.getLogger(__name__)


def _save_to_supabase(rows: list[dict], use_dart: bool) -> None:
    """backtest_runs + backtest_results에 결과 저장."""
    from ..upsert import get_client
    client = get_client()

    run_res = client.table("backtest_runs").insert({
        "dart_used": use_dart,
        "triggered_by": "github_actions" if os.environ.get("GITHUB_RUN_ID") else "manual",
    }).execute()
    run_id = (run_res.data or [{}])[0].get("id")
    if not run_id:
        logger.error("Failed to create backtest_run row")
        return

    records = []
    for r in rows:
        cats = r.get("cats") or {}
        records.append({
            "run_id":          run_id,
            "ticker":          r["ticker"],
            "name":            r["name"],
            "market":          r.get("market"),
            "snapshot_date":   r["snap"],
            "peak_date":       r.get("peak"),
            "actual_x":        float(r["real_x"]) if isinstance(r.get("real_x"), (int, float)) else None,
            "score_10x":       float(r["score"]),
            "passed":          bool(r["passed"]),
            "failed_filters":  r.get("failed") or [],
            "cats":            cats,
            "price_at_snapshot": r.get("price"),
            "rs_score":        r.get("rs_score"),
            "is_target":       r.get("is_target", False),
        })

    client.table("backtest_results").insert(records).execute()
    logger.info("Saved %d backtest results (run_id=%s)", len(records), run_id)

# ── 검증 대상 정의 ──────────────────────────────────────────────────────────
TARGETS = [
    {"ticker": "086520", "name": "에코프로",    "snapshot": "2020-01-02", "peak": "2023-07-26", "actual_x": 107.0, "market": "KOSDAQ"},
    {"ticker": "247540", "name": "에코프로비엠", "snapshot": "2020-01-02", "peak": "2023-07-26", "actual_x":  22.0, "market": "KOSDAQ"},
    {"ticker": "066970", "name": "엘앤에프",    "snapshot": "2020-01-02", "peak": "2022-11-08", "actual_x":  16.0, "market": "KOSDAQ"},
    {"ticker": "042700", "name": "한미반도체",  "snapshot": "2021-01-04", "peak": "2024-06-26", "actual_x":  19.0, "market": "KOSDAQ"},
    {"ticker": "196170", "name": "알테오젠",    "snapshot": "2020-01-02", "peak": "2024-05-14", "actual_x":  50.0, "market": "KOSDAQ"},
    {"ticker": "298040", "name": "효성중공업",  "snapshot": "2022-01-03", "peak": "2024-06-28", "actual_x":  18.0, "market": "KOSPI"},
    # 케이스 스터디 추가 종목
    {"ticker": "012450", "name": "한화에어로스페이스", "snapshot": "2021-06-30", "peak": "2024-12-31", "actual_x": 20.0, "market": "KOSPI"},
    {"ticker": "267260", "name": "HD현대일렉트릭",     "snapshot": "2022-06-30", "peak": "2024-07-31", "actual_x":  8.0, "market": "KOSPI"},
]

CONTROLS = [
    {"ticker": "011070", "name": "LG이노텍",   "snapshot": "2020-01-02", "peak": "2022-12-30", "actual_x":  2.5, "market": "KOSPI"},
    {"ticker": "009150", "name": "삼성전기",   "snapshot": "2020-01-02", "peak": "2022-12-30", "actual_x":  1.8, "market": "KOSPI"},
    {"ticker": "000660", "name": "SK하이닉스", "snapshot": "2020-01-02", "peak": "2022-12-30", "actual_x":  3.5, "market": "KOSPI"},
]

DEFAULT_WEIGHTS = {
    "growth": 28, "momentum": 22, "quality": 18, "sponsorship": 12,
    "value": 8, "safety": 7, "size": 5,
}


def _safe_float(v) -> float | None:
    if v is None:
        return None
    try:
        return float(str(v).replace(",", ""))
    except (ValueError, TypeError):
        return None


def _get_price_data(ticker: str, snapshot_date: str) -> dict:
    """FinanceDataReader로 snapshot_date 기준 1년치 가격 데이터 수집."""
    start = (date.fromisoformat(snapshot_date) - timedelta(days=400)).isoformat()
    result: dict = {}
    try:
        df = fdr.DataReader(ticker, start, snapshot_date)
        if df.empty:
            return result
        df = df.sort_index()

        result["price"] = float(df["Close"].iloc[-1])
        result["price_52w_high"] = float(df["High"].tail(252).max()) if len(df) >= 50 else float(df["High"].max())

        # 20일 평균 거래대금
        recent = df.tail(20)
        avg_vol = float(recent["Volume"].mean())
        avg_close = float(recent["Close"].mean())
        result["avg_daily_value"] = avg_vol * avg_close

        # RS 스코어 (1년 수익률 → 0~100 정규화, +100% = 약 100점)
        if len(df) >= 250:
            price_1y = float(df["Close"].iloc[-250])
            if price_1y > 0:
                ret_1y = (result["price"] - price_1y) / price_1y * 100
                result["rs_score"] = min(100.0, max(0.0, 50.0 + ret_1y * 0.5))
        else:
            result["rs_score"] = 50.0

    except Exception as e:
        logger.warning("Price fetch error %s: %s", ticker, e)
    return result


def _get_actual_multiple(ticker: str, snapshot_date: str, peak_date: str) -> float | None:
    """snapshot_date → peak_date 실제 수익률 계산."""
    try:
        df_start = fdr.DataReader(ticker, snapshot_date, snapshot_date)
        df_peak  = fdr.DataReader(ticker, peak_date,    peak_date)
        if df_start.empty or df_peak.empty:
            return None
        p_start = float(df_start["Close"].iloc[0])
        p_peak  = float(df_peak["Close"].iloc[0])
        return p_peak / p_start if p_start > 0 else None
    except Exception:
        return None


def _get_dart_financials(ticker: str, snapshot_date: str) -> dict:
    """OpenDartReader로 snapshot_date 직전 2년 연간 재무 수집.

    DART_API_KEY가 없으면 빈 dict 반환 (필터는 None → 관대하게 통과).
    """
    api_key = os.environ.get("DART_API_KEY", "")
    if not api_key:
        return {}

    try:
        import OpenDartReader as DartReader
        dart = DartReader(api_key)
        snap_year = date.fromisoformat(snapshot_date).year

        revenues: list[float] = []
        op_incomes: list[float] = []
        debts: list[float] = []
        assets: list[float] = []

        for year in [snap_year - 1, snap_year - 2, snap_year - 3]:
            try:
                # 사업보고서(11011) = Q4/연간
                df = dart.finstate(ticker, year, reprt_code="11011")
                if df is None or df.empty:
                    time.sleep(0.15)
                    continue

                def get_val(kw: str) -> float | None:
                    mask = df["account_nm"].str.contains(kw, na=False)
                    rows = df[mask]
                    if rows.empty:
                        return None
                    v = rows.iloc[0].get("thstrm_amount") or rows.iloc[0].get("당기")
                    return _safe_float(v)

                rev = get_val("매출액") or get_val("수익(매출액)")
                op  = get_val("영업이익")
                debt = get_val("부채총계")
                asset = get_val("자산총계")

                if rev is not None:
                    revenues.append(rev)
                if op is not None:
                    op_incomes.append(op)
                if debt is not None:
                    debts.append(debt)
                if asset is not None:
                    assets.append(asset)

                time.sleep(0.15)
            except Exception as e:
                logger.debug("DART fetch %s %d: %s", ticker, year, e)

        result: dict = {}
        # revenues[0] = 최근년, [1] = 전년, [2] = 2년전
        if len(revenues) >= 1:
            result["revenue_ttm"] = revenues[0]
        if len(revenues) >= 2:
            result["revenue_prev"] = revenues[1]
        if len(revenues) >= 3:
            result["revenue_2y_ago"] = revenues[2]

        # 영업이익률 (최근년)
        if len(revenues) >= 1 and len(op_incomes) >= 1 and revenues[0] > 0:
            result["op_margin_ttm"] = op_incomes[0] / revenues[0] * 100
        if len(revenues) >= 2 and len(op_incomes) >= 2 and revenues[1] > 0:
            result["op_margin_prev"] = op_incomes[1] / revenues[1] * 100

        # 부채비율 (부채총계 / 자본총계 × 100)
        # 자본총계 = 자산총계 - 부채총계
        if debts and assets and len(debts) >= 1 and len(assets) >= 1:
            equity = assets[0] - debts[0]
            if equity > 0:
                result["debt_ratio"] = debts[0] / equity * 100

        return result
    except Exception as e:
        logger.warning("DART financials error %s: %s", ticker, e)
        return {}


def _compute_score(stock_data: dict) -> tuple[float, bool, list[str], dict]:
    """filters_kr + 카테고리 가중합 → (score_10x, passed, failed_filters, cats)."""
    from .filters_kr import apply_kr_filters

    fr = apply_kr_filters(stock_data)

    if not fr.passed:
        return 0.0, False, fr.failed_filters, {}

    # 카테고리별 raw score (score.py _categorize_score와 동일한 로직)
    scores = fr.scores_by_filter
    cats = {
        "growth":      min(100, scores.get("f03", 0) + scores.get("f04", 0)
                          + scores.get("f13_bcr", 0) + scores.get("f14_backlog_growth", 0)),
        "momentum":    min(100, scores.get("f11_rs", 0) + scores.get("f12_momentum", 0)),
        "quality":     min(100, scores.get("f05_op_margin", 0) + scores.get("f05_margin_trend", 0)
                          + scores.get("f15_opm_inflection", 0)
                          + scores.get("f06_roic", 0) + scores.get("f07_fcf", 0)),
        "sponsorship": min(100, scores.get("f10_foreign", 0)),
        "value":       0.0,
        "safety":      min(100, scores.get("safety_score", 5.0)),
        "size":        min(100, scores.get("size_score", 5.0)),
    }
    score_10x = sum(cats[c] * DEFAULT_WEIGHTS.get(c, 0) / 100 for c in cats)
    return round(score_10x, 1), True, [], cats


def run_validation(use_dart: bool = True, save: bool = False) -> None:
    """모든 대상·대조군을 평가하고 결과 테이블 출력."""
    all_stocks = TARGETS + CONTROLS
    rows = []

    for s in all_stocks:
        ticker    = s["ticker"]
        name      = s["name"]
        snap      = s["snapshot"]
        peak      = s["peak"]
        actual_x  = s.get("actual_x", "?")
        is_target = s in TARGETS
        label     = "★타겟" if is_target else "  대조"

        print(f"\n[{label}] {name} ({ticker}) snapshot: {snap}")

        # 1. 가격 데이터
        price_data = _get_price_data(ticker, snap)
        if not price_data:
            print("  NG 가격 데이터 없음 -- 건너뜀")
            continue

        # 2. DART 재무 데이터
        fin_data = _get_dart_financials(ticker, snap) if use_dart else {}
        dart_ok = bool(fin_data)

        # 3. stock_data 합성
        stock_data: dict = {"ticker": ticker, "market": s.get("market", "KOSPI")}
        stock_data.update(price_data)
        stock_data.update(fin_data)

        # 4. 시총 추정 (없으면 None → f01 통과)
        stock_data.setdefault("market_cap", None)
        stock_data.setdefault("order_backlog", None)

        # 5. 점수 계산
        score_10x, passed, failed, cats = _compute_score(stock_data)

        # 6. 실제 수익률 (API 에서 직접 계산)
        real_x = _get_actual_multiple(ticker, snap, peak)

        rows.append({
            "label":     label,
            "ticker":    ticker,
            "name":      name,
            "market":    s.get("market", "KOSPI"),
            "snap":      snap,
            "peak":      peak,
            "score":     score_10x,
            "passed":    passed,
            "failed":    failed,
            "cats":      cats,
            "real_x":    real_x or actual_x,
            "dart_ok":   dart_ok,
            "is_target": is_target,
            "price":     price_data.get("price"),
            "rs_score":  price_data.get("rs_score"),
        })

        passed_str = "OK  통과" if passed else f"NG  탈락 ({', '.join(failed)})"
        print(f"  가격:  {price_data.get('price', '?'):>10,.0f}원 | "
              f"52w고: {price_data.get('price_52w_high', '?'):>10,.0f}원 | "
              f"RS점수: {price_data.get('rs_score', '?'):.0f}")
        if fin_data:
            rev_t = fin_data.get("revenue_ttm")
            rev_p = fin_data.get("revenue_prev")
            if rev_t and rev_p and rev_p > 0:
                rev_g = (rev_t - rev_p) / rev_p * 100
                print(f"  매출성장: {rev_g:+.1f}% | 영업이익률: {fin_data.get('op_margin_ttm', 0) or 0:.1f}% | 부채비율: {fin_data.get('debt_ratio', '?')}")
        else:
            print(f"  재무: DART 미사용 (가격/모멘텀 지표만)")
        print(f"  필터: {passed_str}")
        print(f"  10X점수: {score_10x:.1f} | 실제 수익률: {real_x:.1f}x" if real_x else f"  10X점수: {score_10x:.1f}")

    # ── 결과 요약 테이블 ────────────────────────────────────────────────────
    print("\n" + "=" * 80)
    print("검증 결과 요약")
    print("=" * 80)
    print(f"{'구분':<6} {'종목':<12} {'점수':>6} {'필터':>8} {'실제':>8}  {'성장':>5} {'모멘텀':>6} {'품질':>5}")
    print("-" * 80)

    target_pass = 0
    target_total = 0
    control_pass = 0
    control_total = 0

    for r in rows:
        cats = r["cats"]
        g = cats.get("growth", 0)
        m = cats.get("momentum", 0)
        q = cats.get("quality", 0)
        pass_str = "통과" if r["passed"] else "탈락"
        real_str = f"{r['real_x']:.1f}x" if isinstance(r["real_x"], float) else "?"
        dart_note = "" if r["dart_ok"] else "*"

        print(f"{r['label']:<6} {r['name']:<12} {r['score']:>6.1f} {pass_str:>8} {real_str:>8}{dart_note}  "
              f"{g:>5.0f} {m:>6.0f} {q:>5.0f}")

        if "★" in r["label"]:
            target_total += 1
            if r["passed"]:
                target_pass += 1
        else:
            control_total += 1
            if r["passed"]:
                control_pass += 1

    print("-" * 80)
    print(f"타겟  탐지율: {target_pass}/{target_total} ({target_pass/target_total*100:.0f}% 사전 포착)")
    print(f"대조군 통과율: {control_pass}/{control_total} ({control_pass/control_total*100:.0f}%, 낮을수록 좋음)")
    if target_total > 0 and control_total > 0:
        precision = target_pass / (target_pass + control_pass) if (target_pass + control_pass) > 0 else 0
        print(f"정밀도(Precision): {precision*100:.0f}% (통과 종목 중 실제 타겟 비율)")
    print()
    if not rows[0].get("dart_ok") if rows else True:
        print("* DART_API_KEY 미설정 -- 재무 데이터 없이 가격/모멘텀만 반영됨.")
        print("  정확한 검증을 위해 DART_API_KEY를 설정 후 재실행하세요.")

    if save and rows:
        print("\nSupabase에 결과 저장 중...")
        try:
            _save_to_supabase(rows, use_dart)
            print("저장 완료.")
        except Exception as e:
            logger.error("Supabase 저장 실패: %s", e)


if __name__ == "__main__":
    import argparse
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    parser = argparse.ArgumentParser(description="100배 상승 종목 사전 탐지 검증")
    parser.add_argument("--no-dart", action="store_true", help="DART API 없이 가격·모멘텀만 검증")
    parser.add_argument("--save", action="store_true", help="결과를 Supabase에 저장")
    parser.add_argument("--ticker", help="단일 종목만 검증 (예: 086520)")
    args = parser.parse_args()

    use_dart = not args.no_dart

    if args.ticker:
        # 단일 종목 모드 — TARGETS + CONTROLS에서 찾거나 snapshot 2020-01-02 기본 사용
        all_stocks = TARGETS + CONTROLS
        matched = [s for s in all_stocks if s["ticker"] == args.ticker]
        if not matched:
            matched = [{"ticker": args.ticker, "name": args.ticker, "snapshot": "2020-01-02",
                        "peak": "2023-07-26", "actual_x": None, "market": "KOSPI"}]
        # Run for just this ticker
        for s in matched:
            price_data  = _get_price_data(s["ticker"], s["snapshot"])
            fin_data    = _get_dart_financials(s["ticker"], s["snapshot"]) if use_dart else {}
            stock_data  = {"ticker": s["ticker"], "market": s["market"]}
            stock_data.update(price_data)
            stock_data.update(fin_data)
            stock_data.setdefault("market_cap", None)
            stock_data.setdefault("order_backlog", None)
            score_10x, passed, failed, cats = _compute_score(stock_data)
            print(f"\n=== {s['name']} ({s['ticker']}) @ {s['snapshot']} ===")
            print(f"가격:   {price_data.get('price', '?'):>12,.0f}원")
            print(f"RS점수: {price_data.get('rs_score', '?'):.1f}")
            print(f"재무:   {'DART 데이터 있음' if fin_data else 'DART 없음 (--no-dart 또는 API키 미설정)'}")
            if fin_data:
                print(f"  매출(최근년): {fin_data.get('revenue_ttm', '?')}")
                print(f"  매출(전년):   {fin_data.get('revenue_prev', '?')}")
                print(f"  영업이익률:   {fin_data.get('op_margin_ttm', '?')}")
                print(f"  부채비율:     {fin_data.get('debt_ratio', '?')}")
            print(f"필터:   {'통과' if passed else '탈락 — ' + str(failed)}")
            print(f"점수:   {score_10x:.1f} / 100")
            print(f"카테고리: {cats}")
    else:
        run_validation(use_dart=use_dart, save=args.save)
