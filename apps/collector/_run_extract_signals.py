"""
Re-run extract_signals for all library stocks.
Forces re-extraction to pick up newly backfilled historical data.

Usage:
  python _run_extract_signals.py
  python _run_extract_signals.py --ticker 042700
"""
import os, sys, io, logging
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, 'src')
from dotenv import load_dotenv; load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s',
    datefmt='%H:%M:%S',
)
import argparse
parser = argparse.ArgumentParser()
parser.add_argument('--ticker', help='Process only this ticker')
args = parser.parse_args()

from src.hundredx.extract_signals import run
n = run(ticker_filter=args.ticker, force=True)
print(f"\n=== Done: {n} library entries updated ===")
