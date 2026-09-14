import os
import logging
from dotenv import load_dotenv

# Load .env from apps/collector/.env
load_dotenv("apps/collector/.env")

from apps.collector.src.macro_themes import rank_themes

logging.basicConfig(level=logging.INFO)

def run():
    rows = rank_themes()
    print(f"{'Score':>6} {'Theme':<20} {'Aligned':>7}")
    for r in rows:
        print(f"{r['score']:>6} {r['theme']:<20} {r['aligned']:>7}")

if __name__ == "__main__":
    run()
