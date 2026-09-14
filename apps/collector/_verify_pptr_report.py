"""PPTR Quality Gate verification report — Step 2 (corrected schema)."""
from __future__ import annotations
import os, sys, io
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from dotenv import load_dotenv
load_dotenv()

from supabase import create_client
client = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])

# ── 1. 활성 PPTR 룰 목록 ──────────────────────────────────────────────────────
rules_res = client.table("pptr_rules").select("rule_id, library_ticker, category, created_at").execute()
print(f"[활성 PPTR 룰: {len(rules_res.data)}개]")
for r in rules_res.data:
    print(f"  rule_{r['rule_id']:>3}  ticker={r['library_ticker']:<8}  [{r['category']}]")

# ── 2. 현재 활성 pptr_rule_matches ──────────────────────────────────────────
print("\n\n[현재 활성 pptr_rule_matches (A급 후보)]")
matches = (
    client.table("pptr_rule_matches")
    .select("ticker, rule_id, category, confidence, matched_at, matched_conditions, evidence")
    .order("confidence", desc=True)
    .limit(50)
    .execute()
)
if not matches.data:
    print("  ⚠️  현재 활성 A급 매칭 없음.")
else:
    tickers = list({m["ticker"] for m in matches.data})
    stocks_res = client.table("stocks").select("ticker, name_kr, sector_tag").in_("ticker", tickers).execute()
    stocks_map = {s["ticker"]: s for s in (stocks_res.data or [])}

    for m in matches.data:
        stk = stocks_map.get(m["ticker"], {})
        name = stk.get("name_kr", m["ticker"])
        sector = stk.get("sector_tag", "")
        cat = m.get("category", "")
        conds = m.get("matched_conditions") or []
        conds_str = ", ".join(conds) if isinstance(conds, list) else str(conds)[:60]
        print(f"  {m['ticker']:<8} {name:<22} sector={sector!r:<22} conf={m['confidence']:.3f}  [{cat}]")
        if conds_str:
            print(f"           matched: {conds_str}")

# ── 3. Near-miss 상위 (B/C급) ─────────────────────────────────────────────────
print("\n\n[Near-miss 상위 20개 (B/C급 후보, near_miss_score 기준)]")
near = (
    client.table("pptr_rule_near_misses")
    .select("ticker, rule_id, category, near_miss_score, matched_conditions, missing_conditions, details")
    .order("near_miss_score", desc=True)
    .limit(20)
    .execute()
)
if not near.data:
    print("  (없음)")
else:
    tickers2 = list({m["ticker"] for m in near.data})
    stocks_res2 = client.table("stocks").select("ticker, name_kr, sector_tag").in_("ticker", tickers2).execute()
    stocks_map2 = {s["ticker"]: s for s in (stocks_res2.data or [])}

    for m in near.data:
        stk = stocks_map2.get(m["ticker"], {})
        name = stk.get("name_kr", m["ticker"])
        sector = stk.get("sector_tag", "")
        cat = m.get("category", "")
        missing = m.get("missing_conditions") or []
        missing_str = ", ".join(missing) if isinstance(missing, list) else str(missing)
        matched = m.get("matched_conditions") or []
        matched_str = ", ".join(matched) if isinstance(matched, list) else str(matched)
        print(f"  {m['ticker']:<8} {name:<22} score={m['near_miss_score']:.3f}  [{cat}]  sector={sector!r}")
        if matched_str:
            print(f"           충족: {matched_str}")
        if missing_str:
            print(f"           부족: {missing_str}")

print("\n[완료]")
