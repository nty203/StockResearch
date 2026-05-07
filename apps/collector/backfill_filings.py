import logging
import os
from datetime import date, timedelta
from src.upsert import get_client, upsert_batch
from src.filings_watch import collect_dart_filings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def backfill():
    client = get_client()
    # Targets: Hanwha Engine, Semyung Electric, GST, K-Ensol, Hanmi Semi
    tickers = {'082740', '017510', '083450', '053080', '042700'}
    
    # Fetch 30 days back to catch relevant news mentioned in research
    rows = collect_dart_filings(tickers, lookback_days=30)
    
    if rows:
        count = upsert_batch(client, "filings", rows, on_conflict="ticker,filed_at,filing_type")
        print(f"Backfilled {count} filings for target tickers.")
    else:
        print("No filings found for target tickers in last 30 days matching keywords.")

if __name__ == "__main__":
    backfill()
