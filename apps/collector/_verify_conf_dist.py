"""PPTR confidence distribution and high-confidence matches."""
from __future__ import annotations
import os, sys, io, statistics
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from dotenv import load_dotenv
load_dotenv()
from supabase import create_client
client = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])

# 전체 매칭 신뢰도 분포
all_m = client.table("pptr_rule_matches").select("ticker, rule_id, category, confidence, matched_conditions, matched_at").execute()
confs = [r["confidence"] for r in (all_m.data or [])]

print(f"[전체 pptr_rule_matches: {len(confs)}개]")
if confs:
    confs.sort(reverse=True)
    print(f"  최고: {max(confs):.3f}  최저: {min(confs):.3f}  중앙값: {statistics.median(confs):.3f}")
    for threshold in [0.85, 0.80, 0.75, 0.70, 0.65, 0.60]:
        count = sum(1 for c in confs if c >= threshold)
        print(f"  >= {threshold:.2f}: {count}개")

# A급 고신뢰도 매칭 상세
print("\n[confidence >= 0.70 이상 매칭 (A급 근접)]")
high = [(r, r["confidence"]) for r in (all_m.data or []) if r["confidence"] >= 0.70]
high.sort(key=lambda x: -x[1])

if not high:
    print("  ⚠️  A급 기준(conf>=0.70) 매칭 없음.")
else:
    tickers = list({r[0]["ticker"] for r in high})
    stocks_res = client.table("stocks").select("ticker, name_kr, sector_tag").in_("ticker", tickers).execute()
    stocks_map = {s["ticker"]: s for s in (stocks_res.data or [])}
    seen = set()
    for r, conf in high:
        key = (r["ticker"], r["category"])
        if key in seen:
            continue
        seen.add(key)
        stk = stocks_map.get(r["ticker"], {})
        name = stk.get("name_kr", r["ticker"])
        sector = stk.get("sector_tag", "N/A")
        conds = r.get("matched_conditions") or []
        conds_str = ", ".join(conds) if isinstance(conds, list) else str(conds)
        print(f"  {r['ticker']:<8} {name:<22} conf={conf:.3f}  [{r['category']}]  sector={sector!r}")
        print(f"           matched: {conds_str}")

# 카테고리별 최고 confidence
print("\n[카테고리별 최고 confidence]")
by_cat: dict[str, list] = {}
for r in (all_m.data or []):
    cat = r["category"]
    by_cat.setdefault(cat, []).append(r["confidence"])

for cat, vals in sorted(by_cat.items(), key=lambda x: -max(x[1])):
    print(f"  [{cat:<20}] max={max(vals):.3f}  count={len(vals)}")
