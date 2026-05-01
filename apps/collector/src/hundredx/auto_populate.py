"""End-to-end orchestrator for the user's 3-step workflow:

  Step 1: discover.py — find 100배+ stocks via 5y FDR price scan
  Step 2: extract_signals.py — auto-extract pre-rise signals + categorize
  Step 3: scanner.py (already wired) — apply fingerprints to current stocks

This runs Steps 1+2. Step 3 is the daily collect-hundredx workflow.

Usage:
  uv run python -m src.hundredx.auto_populate
  uv run python -m src.hundredx.auto_populate --years 5 --min-multiplier 30
"""
from __future__ import annotations
import argparse
import logging

from . import discover, extract_signals, backfill_history

logger = logging.getLogger(__name__)


def run(years: int = 5, min_multiplier: float = 50.0,
        skip_backfill: bool = False) -> tuple[int, int, int]:
    """Returns (discovered_count, backfilled_filings, extracted_count)."""
    logger.info("=== Step 1: Discover 100배+ stocks (>= %.0fx in %dy) ===", min_multiplier, years)
    discovered = discover.run(years=years, min_multiplier=min_multiplier, auto_insert=True)
    logger.info("Step 1 complete: %d stocks discovered", len(discovered))

    backfilled = 0
    if not skip_backfill:
        logger.info("=== Step 1b: Backfill historical DART filings around rise_start ===")
        backfilled = backfill_history.run()
        logger.info("Step 1b complete: %d filings backfilled", backfilled)

    logger.info("=== Step 2: Extract pre-rise signals + categorize ===")
    extracted = extract_signals.run(force=backfilled > 0)
    logger.info("Step 2 complete: %d entries got fingerprints", extracted)

    return len(discovered), backfilled, extracted


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser()
    parser.add_argument("--years", type=int, default=5)
    parser.add_argument("--min-multiplier", type=float, default=50.0,
                        help="Default 50x — true 100배 within 5y is rare in KR market")
    parser.add_argument("--skip-backfill", action="store_true",
                        help="Skip DART historical backfill step (faster but signals will be empty)")
    args = parser.parse_args()
    n_disc, n_bf, n_ext = run(
        years=args.years,
        min_multiplier=args.min_multiplier,
        skip_backfill=args.skip_backfill,
    )
    print(f"\n=== Auto-populate done: {n_disc} discovered, {n_bf} backfilled, {n_ext} fingerprinted ===")
