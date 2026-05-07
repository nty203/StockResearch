import os
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[3] / "apps" / "collector"))
from src.upsert import get_client
from src.hundredx.fingerprint_match import match_against_library_entry
from src.utils.db_fetch import bulk_fetch_financials

def deep_scan(min_score=0.5):
    client = get_client()
    
    # Load library
    library = client.table("hundredx_library_stocks").select("*").execute().data or []
    
    # Fetch ALL active stocks with pagination
    all_stocks = []
    page_size = 1000
    for offset in range(0, 5000, page_size):
        res = (
            client.table("stocks")
            .select("ticker, name_kr, sector_tag")
            .eq("is_active", True)
            .in_("market", ["KOSPI", "KOSDAQ"])
            .range(offset, offset + page_size - 1)
            .execute()
        )
        if not res.data:
            break
        all_stocks.extend(res.data)
    
    print(f"Scanning total {len(all_stocks)} stocks...")
    
    results = []
    BATCH_SIZE = 50
    for i in range(0, len(all_stocks), BATCH_SIZE):
        batch = all_stocks[i : i + BATCH_SIZE]
        batch_tickers = [s["ticker"] for s in batch]
        fin_data = bulk_fetch_financials(client, batch_tickers)
        
        # Get filings
        from datetime import timedelta, date
        cutoff = (date.today() - timedelta(days=90)).isoformat()
        filings_res = client.table("filings").select("ticker, headline, raw_text").in_("ticker", batch_tickers).gte("filed_at", cutoff).execute()
        filings_map = {}
        for f in (filings_res.data or []):
            filings_map.setdefault(f["ticker"], []).append(f)
            
        for s in batch:
            ticker = s["ticker"]
            stock_data = fin_data.get(ticker, {})
            stock_data["ticker"] = ticker
            stock_data["sector_tag"] = s.get("sector_tag")
            stock_filings = filings_map.get(ticker, [])
            
            for lib in library:
                m = match_against_library_entry(stock_data, stock_filings, lib)
                if m.score >= min_score:
                    results.append({
                        "ticker": ticker,
                        "name": s["name_kr"],
                        "template": lib["ticker"],
                        "score": m.score,
                        "matched": m.matched_dims
                    })
        if (i // BATCH_SIZE) % 10 == 0:
            print(f"Progress: {i}/{len(all_stocks)}")

    results.sort(key=lambda x: x["score"], reverse=True)
    print(f"\nTop matches found (>= {min_score:.0%}):\n")
    for r in results[:10]:
        print(f"[{r['ticker']}] {r['name']} ({r['score']:.1%}) vs Template {r['template']}")
        print(f"  Matched: {', '.join(r['matched'])}")
        print("-" * 30)

if __name__ == "__main__":
    deep_scan(0.50)
