from __future__ import annotations
import os
import json
from dotenv import load_dotenv
load_dotenv()
from src.upsert import get_client

def get_active_matches():
    client = get_client()
    # Fetch active matches from hundredx_category_matches
    res = (
        client.table("hundredx_category_matches")
        .select("ticker, category, confidence, detected_at, exited_at, llm_verdict")
        .is_("exited_at", "null")
        .order("confidence", desc=True)
        .execute()
    )
    matches = res.data or []
    
    # Fetch stock names
    tickers = list(set(m["ticker"] for m in matches))
    stocks_res = client.table("stocks").select("ticker, name_kr").in_("ticker", tickers).execute()
    stock_map = {s["ticker"]: s["name_kr"] for s in (stocks_res.data or [])}
    
    print(f"Total active matches: {len(matches)}")
    a_grade = [m for m in matches if m["confidence"] >= 0.8]
    b_grade = [m for m in matches if 0.7 <= m["confidence"] < 0.8]
    
    print(f"\n[A-Grade Matches (conf >= 0.8)] - {len(a_grade)}")
    for m in a_grade:
        name = stock_map.get(m["ticker"], m["ticker"])
        print(f"[{m['ticker']}] {name} - Category: {m['category']}, Confidence: {m['confidence']}, Detected: {m['detected_at']}")
        print(f"LLM Verdict: {m['llm_verdict']}")
        print("-" * 40)

    print(f"\n[B-Grade / Near-Miss (0.7 <= conf < 0.8)] - {len(b_grade)}")
    for m in b_grade:
        name = stock_map.get(m["ticker"], m["ticker"])
        print(f"[{m['ticker']}] {name} - Category: {m['category']}, Confidence: {m['confidence']}, Detected: {m['detected_at']}")
        print("-" * 40)

if __name__ == "__main__":
    get_active_matches()
