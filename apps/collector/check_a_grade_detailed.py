import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))
from dotenv import load_dotenv
load_dotenv()
from supabase import create_client
client = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])

print("### Active PPTR A-Grade Matches ###")
matches = client.table("hundredx_category_matches").select(
    "ticker, category, confidence"
).is_("exited_at", "null").order("confidence", desc=True).execute()

for m in (matches.data or []):
    stk = client.table("stocks").select("name_kr, sector_tag").eq("ticker", m["ticker"]).execute()
    name = stk.data[0].get("name_kr", m["ticker"]) if stk.data else m["ticker"]
    sector = stk.data[0].get("sector_tag", "") if stk.data else ""
    print(f"- {m['ticker']} {name} (Sector: {sector}, Rule: {m['category']}, Confidence: {m['confidence']:.3f})")

print("\n### Near-Miss / B-Grade Candidates (Confidence < 0.35) ###")
# Just a sample
near_misses = client.table("hundredx_category_matches").select(
    "ticker, category, confidence"
).is_("exited_at", "null").lt("confidence", 0.35).limit(5).execute()

for m in (near_misses.data or []):
    stk = client.table("stocks").select("name_kr, sector_tag").eq("ticker", m["ticker"]).execute()
    name = stk.data[0].get("name_kr", m["ticker"]) if stk.data else m["ticker"]
    sector = stk.data[0].get("sector_tag", "") if stk.data else ""
    print(f"- {m['ticker']} {name} (Sector: {sector}, Rule: {m['category']}, Confidence: {m['confidence']:.3f})")
