import os
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[3] / "apps" / "collector"))
from src.upsert import get_client

def check_tickers():
    client = get_client()
    tickers = ["082740", "077970", "083450", "105110", "042700"]
    
    res = (
        client.table("hundredx_category_matches")
        .select("ticker, category, fingerprint_score, confidence, fingerprint_dims")
        .in_("ticker", tickers)
        .execute()
    )
    
    matches = res.data or []
    if not matches:
        print("None of the target tickers have active matches.")
        return

    print(f"Found matches for target tickers:\n")
    for m in matches:
        print(f"[{m['ticker']}] Category: {m['category']}")
        print(f"  Fingerprint Score: {m['fingerprint_score']:.1%}" if m['fingerprint_score'] else "  Fingerprint Score: N/A")
        print(f"  Confidence: {m['confidence']:.2f}")
        print("-" * 30)

if __name__ == "__main__":
    check_tickers()
