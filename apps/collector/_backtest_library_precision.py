"""백테스트 — 라이브러리 100배 종목의 fingerprint quant 분포가 어떤 임계값에서 정렬되는지 측정.

목적: 새 fingerprint 지표 (f_score, gp_to_assets, accruals_ratio, roic, revenue_qoq_acc)가
실제 100배 종목의 사전 신호로서 유의미한 분포를 가지는지 통계적으로 확인.

출력: 카테고리별 / 전체 라이브러리에 대해
  - 각 지표의 평균/중앙값/표준편차
  - 임계값(percentile) 후보 — 추후 fingerprint score 게이트 튜닝에 사용
"""
import os, sys, io, statistics
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, 'src')
from dotenv import load_dotenv; load_dotenv()

from supabase import create_client

SUPABASE_URL = os.environ['SUPABASE_URL']
SUPABASE_KEY = os.environ['SUPABASE_SERVICE_KEY']
client = create_client(SUPABASE_URL, SUPABASE_KEY)

DIMS = [
    "f_score_at_signal",
    "gp_to_assets_at_signal",
    "accruals_ratio_at_signal",
    "roic_at_signal",
    "fcf_margin_at_signal",
    "revenue_qoq_acceleration_at_signal",
    "opm_at_signal",
    "opm_delta_at_signal",
    "revenue_growth_yoy",
    "debt_ratio_at_signal",
]


def percentile(data, p):
    if not data: return None
    s = sorted(data)
    k = (len(s) - 1) * p / 100
    f = int(k); c = min(f + 1, len(s) - 1)
    return s[f] + (s[c] - s[f]) * (k - f)


def main():
    res = client.table("hundredx_library_stocks").select(
        "ticker, category, pre_rise_signals"
    ).execute()
    rows = res.data or []
    print(f"\n100배 라이브러리: {len(rows)}개 종목\n")

    # 전체 통계
    print("=" * 70)
    print("전체 라이브러리 — 지표별 분포")
    print("=" * 70)
    for dim in DIMS:
        vals = []
        for row in rows:
            q = (row.get("pre_rise_signals") or {}).get("quant") or {}
            v = q.get(dim)
            if v is not None:
                vals.append(v)
        if not vals:
            print(f"  {dim:<38} ❌ no data")
            continue
        mean = statistics.mean(vals)
        med = statistics.median(vals)
        std = statistics.stdev(vals) if len(vals) > 1 else 0
        p25 = percentile(vals, 25)
        p75 = percentile(vals, 75)
        print(f"  {dim:<38} N={len(vals):>2}  mean={mean:>8.2f}  median={med:>8.2f}  "
              f"std={std:>7.2f}  p25={p25:>7.2f}  p75={p75:>7.2f}")

    # 카테고리별 핵심 지표 평균
    print("\n" + "=" * 70)
    print("카테고리별 평균 (핵심 지표만)")
    print("=" * 70)
    by_cat = {}
    for row in rows:
        by_cat.setdefault(row["category"], []).append(row)
    headline_dims = ["f_score_at_signal", "roic_at_signal", "gp_to_assets_at_signal",
                     "revenue_qoq_acceleration_at_signal", "opm_at_signal"]
    print(f"  {'category':<22} | {'N':>2} | ", " | ".join(f"{d[:12]:>12}" for d in headline_dims))
    print("  " + "-" * 100)
    for cat, items in sorted(by_cat.items()):
        line = f"  {cat:<22} | {len(items):>2} | "
        cells = []
        for dim in headline_dims:
            vals = []
            for row in items:
                q = (row.get("pre_rise_signals") or {}).get("quant") or {}
                v = q.get(dim)
                if v is not None: vals.append(v)
            cells.append(f"{statistics.mean(vals):>12.2f}" if vals else "         N/A")
        print(line + " | ".join(cells))

    # 임계값 제안
    print("\n" + "=" * 70)
    print("임계값 제안 (전체 라이브러리 p25 기준 — 신뢰 게이트로 적합)")
    print("=" * 70)
    suggestions = {
        "f_score_at_signal":               ("≥", 6, "Piotroski 강한 펀더멘털"),
        "gp_to_assets_at_signal":          ("≥", 0.25, "Novy-Marx 임계"),
        "accruals_ratio_at_signal":        ("≤", 0.05, "Sloan 현금이익 우수"),
        "roic_at_signal":                  ("≥", 9.0, "Phelps 100-to-1 기준 (%)"),
        "revenue_qoq_acceleration_at_signal": ("≥", 5.0, "Asness 매출가속 (pp)"),
    }
    for dim, (op, val, desc) in suggestions.items():
        vals = []
        for row in rows:
            q = (row.get("pre_rise_signals") or {}).get("quant") or {}
            v = q.get(dim)
            if v is not None: vals.append(v)
        if vals:
            if op == "≥":
                hit = sum(1 for v in vals if v >= val)
            else:
                hit = sum(1 for v in vals if v <= val)
            pct = hit / len(vals) * 100
            print(f"  {dim:<38} {op} {val:<6} → {hit}/{len(vals)} ({pct:.0f}%)  {desc}")


if __name__ == "__main__":
    main()
