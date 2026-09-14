"""PPTR Verify — hundredx_category_matches 테이블 A급 상태 확인."""
from __future__ import annotations
import os, sys, io
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from dotenv import load_dotenv
load_dotenv()
from supabase import create_client
client = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])

# hundredx_category_matches 스키마 확인
m = client.table("hundredx_category_matches").select("*").limit(1).execute()
if m.data:
    print("hundredx_category_matches columns:", list(m.data[0].keys()))
    print("sample:", {k: v for k, v in m.data[0].items() if k not in ("evidence", "confidence_breakdown")})
print()

# 활성 매칭 (exited_at IS NULL) 전체
active = (
    client.table("hundredx_category_matches")
    .select("ticker, category, confidence, exited_at, detected_at")
    .is_("exited_at", "null")
    .order("confidence", desc=True)
    .execute()
)
print(f"[hundredx_category_matches 활성 (exited_at IS NULL): {len(active.data)}개]")

if active.data:
    tickers = list({r["ticker"] for r in active.data})
    stocks_res = client.table("stocks").select("ticker, name_kr, sector_tag").in_("ticker", tickers).execute()
    stocks_map = {s["ticker"]: s for s in (stocks_res.data or [])}

    for r in active.data:
        stk = stocks_map.get(r["ticker"], {})
        name = stk.get("name_kr", r["ticker"])
        sector = stk.get("sector_tag", "N/A")
        print(f"  {r['ticker']:<8} {name:<22} conf={r['confidence']:.3f}  [{r['category']}]  sector={sector!r}")
else:
    print("  (없음)")

# 신뢰도 분포
all_m = client.table("hundredx_category_matches").select("confidence, category").is_("exited_at", "null").execute()
confs = [r["confidence"] for r in (all_m.data or []) if r["confidence"] is not None]
if confs:
    import statistics
    print(f"\n활성 confidence 분포: 최고={max(confs):.3f}, 최저={min(confs):.3f}, 중앙값={statistics.median(confs):.3f}")
    for t in [0.90, 0.85, 0.80, 0.75, 0.70]:
        print(f"  >= {t:.2f}: {sum(1 for c in confs if c >= t)}개")
