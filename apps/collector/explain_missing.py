import os
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[3] / "apps" / "collector"))
from src.upsert import get_client

def explain_missing():
    client = get_client()
    tickers = ["082740", "077970", "083450", "105110", "042700"] # Hanwha, STX, GST, K-Ensol, Hanmi
    
    # 1. Check in matches
    res = (
        client.table("hundredx_category_matches")
        .select("ticker, category, confidence, exited_at")
        .in_("ticker", tickers)
        .execute()
    )
    matches = res.data or []
    
    # 2. Check in library
    lib_res = (
        client.table("hundredx_library_stocks")
        .select("ticker, category")
        .in_("ticker", tickers)
        .execute()
    )
    lib_entries = lib_res.data or []

    print("--- Analysis Result ---")
    for t in tickers:
        m_list = [m for m in matches if m["ticker"] == t]
        l_list = [l for l in lib_entries if l["ticker"] == t]
        
        print(f"[{t}]")
        if m_list:
            for m in m_list:
                status = "EXITED" if m["exited_at"] else "ACTIVE"
                print(f"  - Signal found: {m['category']} (Conf: {m['confidence']:.2f}, Status: {status})")
        else:
            print("  - No automated signal detected yet.")
            
        if l_list:
            print(f"  - Registered in Library: {', '.join(l['category'] for l in l_list)}")
        else:
            print("  - Not registered in Library.")
        print("-" * 20)

if __name__ == "__main__":
    explain_missing()
