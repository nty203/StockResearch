"""상폐/거래정지 종목 자동 감지 → is_active=False 및 활성 매치 exit.

판정 기준:
  최근 14영업일 가격 데이터에서 모두 volume=0 AND open=0
  → 매매 정지 또는 상폐 (KRX 데이터에서 일관된 패턴)

처리:
  1. stocks.is_active=False 로 변경 (Scanner가 다음 회차부터 자동 제외)
  2. hundredx_category_matches 의 활성 매치(exited_at IS NULL) 종료
  3. llm_verdict='confirm' 이었더라도 종료 (상폐 종목은 신호 무효)

실행:
  python -m utils.prune_delisted              # 실제 적용
  python -m utils.prune_delisted --dry-run    # 점검만
  python -m utils.prune_delisted --days 21    # 윈도우 변경
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# 직접 실행 시 module path 보정
if __package__ is None:
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))

import psycopg2
from psycopg2.extras import Json
from dotenv import load_dotenv


SUSPECT_SQL = """
WITH last_n AS (
    SELECT
        p.ticker,
        COUNT(*) AS total_days,
        COUNT(*) FILTER (WHERE p.volume = 0) AS zero_vol_days,
        COUNT(*) FILTER (WHERE p.open = 0) AS zero_open_days,
        MAX(p.date) AS last_date
    FROM prices_daily p
    WHERE p.date >= CURRENT_DATE - %s::int * INTERVAL '1 day'
    GROUP BY p.ticker
    HAVING COUNT(*) >= %s
)
SELECT
    l.ticker, s.name_kr, s.market, l.total_days, l.last_date
FROM last_n l
JOIN stocks s ON s.ticker = l.ticker
WHERE l.zero_vol_days = l.total_days
  AND l.zero_open_days = l.total_days
  AND s.is_active = TRUE
ORDER BY s.market, l.ticker;
"""


def detect_and_prune(window_days: int = 21, min_days: int = 7, dry_run: bool = False) -> dict:
    load_dotenv()
    db_url = os.environ["SUPABASE_DB_URL"]
    now = datetime.now(timezone.utc)

    with psycopg2.connect(db_url) as conn:
        with conn.cursor() as cur:
            cur.execute(SUSPECT_SQL, (window_days, min_days))
            suspects = cur.fetchall()

        if not suspects:
            logger.info("No delisted/halted suspects found.")
            return {"detected": 0, "deactivated": 0, "matches_exited": 0}

        logger.info("Detected %d delisted/halted suspects", len(suspects))
        for ticker, name, market, days, last_date in suspects:
            logger.info("  %s %s (%s) — %d일 연속 volume=0 open=0, last=%s",
                        ticker, name, market, days, last_date)

        if dry_run:
            return {"detected": len(suspects), "deactivated": 0, "matches_exited": 0, "dry_run": True}

        tickers = [row[0] for row in suspects]

        # 1. is_active=False
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE stocks SET is_active = FALSE WHERE ticker = ANY(%s)",
                (tickers,),
            )
            deactivated = cur.rowcount

        # 2. 활성 매치 exit
        exit_reason = {
            "source_type": "system_event",
            "source_id": f"prune_delisted_{now.date().isoformat()}",
            "text_excerpt": f"상폐/거래정지 자동 감지 — {window_days}일 윈도우 거래 정지",
            "date": now.date().isoformat(),
            "amount": None,
        }
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE hundredx_category_matches
                SET exited_at = %s,
                    evidence = COALESCE(evidence, '[]'::jsonb) || %s
                WHERE ticker = ANY(%s) AND exited_at IS NULL
                """,
                (now.isoformat(), Json([exit_reason]), tickers),
            )
            exited = cur.rowcount

        conn.commit()
        logger.info("Deactivated %d stocks, exited %d active matches", deactivated, exited)

        return {
            "detected": len(suspects),
            "deactivated": deactivated,
            "matches_exited": exited,
            "tickers": tickers,
        }


def main() -> int:
    parser = argparse.ArgumentParser(description="Detect & prune delisted/halted KR stocks")
    parser.add_argument("--days", type=int, default=21, help="lookback window (calendar days)")
    parser.add_argument("--min-days", type=int, default=7, help="min observations within window")
    parser.add_argument("--dry-run", action="store_true", help="detect only, do not modify DB")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    result = detect_and_prune(args.days, args.min_days, args.dry_run)
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
