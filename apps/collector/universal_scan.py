import os
import sys
import logging
from pathlib import Path
from datetime import datetime, timezone

# Add collector src to path
sys.path.append(str(Path(__file__).resolve().parents[3] / "apps" / "collector"))

from src.upsert import get_client
from src.hundredx.fingerprint_match import match_against_library_entry
from src.utils.db_fetch import bulk_fetch_financials

def universal_scan(min_score: float = 0.8):
    client = get_client()
    
    # 1. Load library
    lib_res = client.table("hundredx_library_stocks").select("*").execute()
    library = lib_res.data or []
    print(f"Loaded {len(library)} library templates.")

    # 2. Fetch active KR stocks
    stocks_res = (
        client.table("stocks")
        .select("ticker, name_kr, sector_tag")
        .eq("is_active", True)
        .in_("market", ["KOSPI", "KOSDAQ"])
        .execute()
    )
    stocks = stocks_res.data or []
    print(f"Scanning {len(stocks)} KR stocks...")

    # 3. Process in batches to get filings + financials
    BATCH_SIZE = 50
    high_matches = []

    for i in range(0, len(stocks), BATCH_SIZE):
        batch = stocks[i : i + BATCH_SIZE]
        batch_tickers = [s["ticker"] for s in batch]
        
        # Fetch financials
        fin_data = bulk_fetch_financials(client, batch_tickers)
        
        # Fetch filings (last 90 days)
        from datetime import timedelta, date
        cutoff = (date.today() - timedelta(days=90)).isoformat()
        filings_res = (
            client.table("filings")
            .select("ticker, headline, raw_text")
            .in_("ticker", batch_tickers)
            .gte("filed_at", cutoff)
            .execute()
        )
        filings_map = {}
        for f in (filings_res.data or []):
            filings_map.setdefault(f["ticker"], []).append(f)

        for s in batch:
            ticker = s["ticker"]
            stock_data = fin_data.get(ticker, {})
            stock_data["ticker"] = ticker
            stock_data["sector_tag"] = s.get("sector_tag")
            stock_filings = filings_map.get(ticker, [])

            for lib_entry in library:
                match = match_against_library_entry(stock_data, stock_filings, lib_entry)
                if match.score >= min_score:
                    high_matches.append({
                        "ticker": ticker,
                        "name": s["name_kr"],
                        "template_ticker": lib_entry["ticker"],
                        "template_name": lib_entry.get("notes", "").split(":")[0],
                        "score": match.score,
                        "matched": match.matched_dims,
                        "missing": match.missing_dims
                    })

        if (i // BATCH_SIZE) % 5 == 0:
            print(f"Progress: {i}/{len(stocks)}...")

    print(f"\nFound {len(high_matches)} high-match candidates (>= {min_score:.0%}):\n")
    high_matches.sort(key=lambda x: x["score"], reverse=True)
    for h in high_matches[:20]:
        print(f"[{h['ticker']}] {h['name']} -> {h['template_name']} ({h['template_ticker']})")
        print(f"  Score: {h['score']:.1%}")
        print(f"  Matched: {', '.join(h['matched'])}")
        print("-" * 30)

if __name__ == "__main__":
    universal_scan(0.60)
