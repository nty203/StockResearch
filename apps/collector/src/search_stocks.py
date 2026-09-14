import os
import sys
import json
import logging
import datetime
from collections import defaultdict
from typing import List, Dict, Any
from dotenv import load_dotenv
from supabase import create_client

# Add src to sys.path if needed
sys.path.insert(0, os.path.dirname(__file__))

from .upsert import get_client, retry_execute

logger = logging.getLogger(__name__)

def search_relevant_stocks(keywords: List[str], limit: int = 15) -> List[Dict[str, Any]]:
    """
    Search for stocks dynamically based on keywords across multiple tables.
    Prioritizes stocks that match multiple keywords or are in the library.
    """
    client = get_client()
    
    # Track match counts for relevance sorting
    match_data = defaultdict(lambda: {"ticker": "", "name": "", "reasons": [], "score_adj": 0})

    for kw in keywords:
        if len(kw) < 2: continue
        
        # 1. Library Search (Weighted highly)
        res_lib = retry_execute(
            lambda: client.table("hundredx_library_stocks")
            .select("ticker,category,notes")
            .or_(f"category.ilike.%{kw}%,notes.ilike.%{kw}%")
            .execute()
        )
        for m in (res_lib.data or []):
            t = m["ticker"]
            match_data[t]["ticker"] = t
            match_data[t]["reasons"].append(f"Library({m['category']})")
            match_data[t]["score_adj"] += 15 # High priority for library stocks

        # 2. Active Matches Search
        res_act = retry_execute(
            lambda: client.table("hundredx_category_matches")
            .select("ticker,category,confidence")
            .is_("exited_at", "null")
            .ilike("category", f"%{kw}%")
            .execute()
        )
        for m in (res_act.data or []):
            t = m["ticker"]
            match_data[t]["ticker"] = t
            match_data[t]["reasons"].append(f"Active({m['category']})")
            match_data[t]["score_adj"] += 10 + (m["confidence"] * 5)

        # 3. Raw Stock Names (Specific companies often mentioned in news)
        res_stk = retry_execute(
            lambda: client.table("stocks")
            .select("ticker,name_kr")
            .ilike("name_kr", f"%{kw}%")
            .execute()
        )
        for m in (res_stk.data or []):
            t = m["ticker"]
            match_data[t]["ticker"] = t
            match_data[t]["name"] = m["name_kr"]
            match_data[t]["reasons"].append(f"Name match")
            match_data[t]["score_adj"] += 5

    # Filter and Fetch Names for all candidates
    candidates = []
    for t, data in match_data.items():
        if not data["name"]:
            stk = retry_execute(
                lambda: client.table("stocks").select("name_kr").eq("ticker", t).execute()
            ).data
            data["name"] = stk[0]["name_kr"] if stk else t
        
        # Bonus for multiple keyword hits
        relevance_score = data["score_adj"] + (len(set(data["reasons"])) * 5)
        candidates.append({**data, "relevance": relevance_score})

    # Sort by relevance
    candidates.sort(key=lambda x: x["relevance"], reverse=True)

    # 4. Filter and Score based on Momentum (prices_daily)
    results = []
    for c in candidates[:limit*2]:
        # Fetch last 60 days price
        prices = retry_execute(
            lambda: client.table("prices_daily")
            .select("close")
            .eq("ticker", c["ticker"])
            .order("date", desc=True)
            .limit(260)
            .execute()
        ).data
        
        if not prices or len(prices) < 20:
            continue
            
        close_list = [float(p["close"]) for p in prices]
        curr = close_list[0]
        high52 = max(close_list)
        n52 = (curr / high52) * 100
        r1 = (curr / close_list[20] - 1) * 100 if len(close_list) >= 20 else 0
        r3 = (curr / close_list[60] - 1) * 100 if len(close_list) >= 60 else 0
        
        # Scoring logic aligned with macro-idea.md
        if 88 <= n52 <= 99:
            early, flag = 50, "🔺임박"
        elif 99 < n52 <= 112:
            early, flag = 40, "✅돌파직후"
        elif n52 > 112:
            early, flag = 30, "⚠️과열"
        elif 80 <= n52 < 88:
            early, flag = 30, "📌중기후보"
        else:
            early, flag = 20, "🔵하단"
            
        penalty = min(30, max(0, r3 - 60) / 2)
        score = round(early - penalty + max(0, min(15, r1)), 1)
        
        results.append({
            "ticker": c["ticker"],
            "name": c["name"],
            "role": "밸류체인", # Default role
            "near_52w_high": round(n52, 1),
            "ret_1m": round(r1, 1),
            "ret_3m": round(r3, 1),
            "early_signal_score": score,
            "signal_flag": flag,
            "discovery_reason": ", ".join(set(c["reasons"]))
        })

    # 5. Fetch recent broker reports
    tickers = [r["ticker"] for r in results]
    if tickers:
        thirty_days_ago = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=30)).strftime("%Y-%m-%d")
        reports = retry_execute(
            lambda: client.table("broker_reports")
            .select("ticker, firm, title, date")
            .in_("ticker", tickers)
            .gte("date", thirty_days_ago)
            .order("date", desc=True)
            .execute()
        ).data or []
        
        reports_by_ticker = defaultdict(list)
        for r in reports:
            reports_by_ticker[r["ticker"]].append(f"{r['firm']}({r['date']}): {r['title']}")
            
        for res in results:
            if res["ticker"] in reports_by_ticker:
                res["recent_broker_reports"] = " | ".join(reports_by_ticker[res["ticker"]][:2])
            else:
                res["recent_broker_reports"] = ""

    # Sort by score and limit
    results.sort(key=lambda x: x["early_signal_score"], reverse=True)
    return results[:limit]

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m src.search_stocks <keyword1> <keyword2>...")
        sys.exit(1)
    
    sys.stdout.reconfigure(encoding='utf-8')
    
    # Load env from common locations
    env_paths = [".env", "apps/web/.env.local", "apps/collector/.env"]
    for p in env_paths:
        if os.path.exists(p):
            load_dotenv(p)
            
    keywords = sys.argv[1:]
    found = search_relevant_stocks(keywords)
    print(json.dumps(found, indent=2, ensure_ascii=False))
