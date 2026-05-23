"""Analyze Library PPTR — 라이브러리 종목들에 대해 PPTR 7단계를 생성하여 DB에 저장.

Usage:
  uv run python -m src.hundredx.analyze_library_pptr
  uv run python -m src.hundredx.analyze_library_pptr --ticker 012450
"""
from __future__ import annotations
import argparse
import logging
import json

from ..upsert import get_client
from . import pptr_engine

logger = logging.getLogger(__name__)


def run(ticker: str | None = None) -> int:
    client = get_client()

    query = client.table("hundredx_library_stocks").select("*")
    if ticker:
        query = query.eq("ticker", ticker)
    
    res = query.execute()
    rows = res.data or []

    if not rows:
        logger.info("No library stocks found.")
        return 0

    logger.info("Found %d library stocks to analyze.", len(rows))
    
    updated_count = 0
    for row in rows:
        t = row.get("ticker")
        cat = row.get("category")
        
        try:
            pptr_data = pptr_engine.generate_pptr(row)
            
            # Upsert back to DB
            client.table("hundredx_library_stocks").update({
                "pptr_analysis": pptr_data
            }).eq("ticker", t).eq("category", cat).execute()
            
            updated_count += 1
            logger.info("Generated PPTR for %s (%s)", t, cat)
        except Exception as e:
            logger.error("Failed to generate PPTR for %s: %s", t, e)

    return updated_count


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser()
    parser.add_argument("--ticker", type=str, help="Specific ticker to analyze")
    args = parser.parse_args()

    count = run(ticker=args.ticker)
    print(f"\n=== Successfully generated PPTR for {count} library stocks ===")
