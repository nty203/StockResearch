"""현재 엔진/조선 종목 category_matches 상태 확인."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))
if sys.stdout.encoding != 'utf-8':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from dotenv import load_dotenv
load_dotenv()
from supabase import create_client
client = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])

print("[엔진/조선 종목 현재 매칭 상태]")
for ticker in ["082740", "077970", "071970", "443060"]:
    matches = client.table("hundredx_category_matches").select(
        "ticker, category, confidence, exited_at"
    ).eq("ticker", ticker).execute()
    stk = client.table("stocks").select("name_kr").eq("ticker", ticker).execute()
    name = stk.data[0]["name_kr"] if stk.data else ticker
    active = [m for m in (matches.data or []) if not m.get("exited_at")]
    exited = [m for m in (matches.data or []) if m.get("exited_at")]
    print(f"\n{ticker} {name}:")
    for m in active:
        print(f"  ACTIVE  {m['category']} conf={m['confidence']:.3f}")
    for m in exited:
        print(f"  EXITED  {m['category']} conf={m['confidence']:.3f}  ({(m.get('exited_at') or '')[:10]})")

# 임상_파이프라인 전체 활성 매칭 + 섹터 확인
print("\n\n[임상_파이프라인 전체 활성 매칭]")
clinical = client.table("hundredx_category_matches").select(
    "ticker, category, confidence"
).eq("category", "임상_파이프라인").is_("exited_at", "null").order("confidence", desc=True).execute()
for row in (clinical.data or []):
    stk = client.table("stocks").select("name_kr, sector_tag").eq("ticker", row["ticker"]).execute()
    name = stk.data[0].get("name_kr", row["ticker"]) if stk.data else row["ticker"]
    sector = stk.data[0].get("sector_tag", "") if stk.data else ""
    print(f"  {row['ticker']:<8} {name:<20} sector={sector!r:<20} conf={row['confidence']:.3f}")
