import os
import sys
from pathlib import Path

# Add collector src to path
sys.path.append(str(Path(__file__).resolve().parents[3] / "apps" / "collector"))

from src.upsert import get_client

def find_high_matches():
    client = get_client()
    
    # Query all active matches with fingerprint_score >= 0.8 (starting a bit lower to see context)
    res = (
        client.table("hundredx_category_matches")
        .select("ticker, category, fingerprint_score, confidence, fingerprint_dims")
        .gte("fingerprint_score", 0.8)
        .is_("exited_at", "null")
        .order("fingerprint_score", desc=True)
        .execute()
    )
    
    matches = res.data or []
    if not matches:
        print("No matches found with fingerprint_score >= 0.8")
        return

    # Get names
    tickers = [m["ticker"] for m in matches]
    stocks_res = client.table("stocks").select("ticker, name_kr").in_("ticker", tickers).execute()
    name_map = {s["ticker"]: s["name_kr"] for s in (stocks_res.data or [])}

    print(f"Found {len(matches)} matches with fingerprint_score >= 0.8:\n")
    for m in matches:
        name = name_map.get(m["ticker"], "Unknown")
        print(f"[{m['ticker']}] {name}")
        print(f"  Category: {m['category']}")
        print(f"  Fingerprint Score: {m['fingerprint_score']:.1%}")
        print(f"  Confidence: {m['confidence']:.2f}")
        dims = m.get("fingerprint_dims") or {}
        print(f"  Matched: {', '.join(dims.get('matched', []))}")
        print(f"  Missing: {', '.join(dims.get('missing', []))}")
        print("-" * 30)

if __name__ == "__main__":
    find_high_matches()
