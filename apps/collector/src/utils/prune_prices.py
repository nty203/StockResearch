"""Prune prices_daily to keep only 2 years of data.

Run AFTER hundredx update_library completes (collect-weekly.yml sequential step).

Note: hundredx update_library uses prices for rise_start_date baseline. The
fallback in update_library handles missing historical prices gracefully (uses
oldest available), so pruning >2y data is safe.

구현 전략:
  1. psycopg2 직접 연결 사용 → REST API statement timeout(3초) 회피
  2. 1일 단위 DELETE (WINDOW_DAYS=1 기본) → 각 쿼리 빠름
  3. continue-on-error: true in workflow → 실패해도 전체 비致命
"""
from __future__ import annotations
import logging
import os
from datetime import date, timedelta

logger = logging.getLogger(__name__)

RETENTION_DAYS = 730
WINDOW_DAYS = int(os.environ.get("PRICE_PRUNE_WINDOW_DAYS", "1"))
MAX_DELETE_DAYS = int(os.environ.get("PRICE_PRUNE_MAX_DAYS", "30"))  # 1회 실행 최대 N일 처리


def _prune_via_psycopg2(cutoff: str, window_days: int, max_days: int) -> int:
    """Direct psycopg2 연결로 prune — REST timeout 없음."""
    import psycopg2
    db_url = os.environ.get("SUPABASE_DB_URL", "")
    if not db_url:
        raise RuntimeError("SUPABASE_DB_URL not set")

    conn = psycopg2.connect(db_url)
    conn.autocommit = True
    cur = conn.cursor()

    # 가장 오래된 날짜 확인
    cur.execute("SELECT MIN(date) FROM prices_daily WHERE date < %s", (cutoff,))
    row = cur.fetchone()
    if not row or not row[0]:
        logger.info("No price rows older than %s", cutoff)
        conn.close()
        return 0

    start = row[0] if isinstance(row[0], date) else date.fromisoformat(str(row[0])[:10])
    cutoff_date = date.fromisoformat(cutoff)
    total = 0
    processed_days = 0

    while start < cutoff_date and processed_days < max_days:
        end = min(start + timedelta(days=window_days), cutoff_date)
        try:
            cur.execute(
                "DELETE FROM prices_daily WHERE date >= %s AND date < %s",
                (start.isoformat(), end.isoformat())
            )
            deleted = cur.rowcount
            total += deleted
            if deleted > 0:
                logger.info("Pruned %d rows: %s ~ %s", deleted, start, end)
        except Exception as e:
            logger.warning("Delete failed for %s ~ %s: %s", start, end, e)
        start = end
        processed_days += window_days

    conn.close()
    if start < cutoff_date:
        logger.info("Partial prune: processed %d days (remaining up to %s)", processed_days, cutoff_date)
    return total


def _prune_via_rest(client, cutoff: str, window_days: int, max_days: int) -> int:
    """Supabase REST client 폴백 (psycopg2 없을 때)."""
    res = (
        client.table("prices_daily")
        .select("date")
        .lt("date", cutoff)
        .order("date")
        .limit(1)
        .execute()
    )
    rows = res.data or []
    if not rows:
        return 0

    start = date.fromisoformat(str(rows[0]["date"])[:10])
    cutoff_date = date.fromisoformat(cutoff)
    total = 0
    processed_days = 0

    while start < cutoff_date and processed_days < max_days:
        end = min(start + timedelta(days=window_days), cutoff_date)
        try:
            r = (
                client.table("prices_daily")
                .delete()
                .gte("date", start.isoformat())
                .lt("date", end.isoformat())
                .execute()
            )
            deleted = len(r.data or [])
            total += deleted
            if deleted > 0:
                logger.info("Pruned %d rows: %s ~ %s", deleted, start, end)
        except Exception as e:
            logger.warning("REST delete failed for %s ~ %s: %s (skipping window)", start, end, e)
        start = end
        processed_days += window_days

    return total


def run() -> int:
    cutoff_date = date.today() - timedelta(days=RETENTION_DAYS)
    cutoff = cutoff_date.isoformat()
    window_days = max(1, WINDOW_DAYS)
    max_days = max(1, MAX_DELETE_DAYS)

    # 1순위: psycopg2 직접 연결 (timeout 없음)
    if os.environ.get("SUPABASE_DB_URL"):
        try:
            count = _prune_via_psycopg2(cutoff, window_days, max_days)
            logger.info("psycopg2 prune complete: %d rows deleted", count)
            return count
        except Exception as e:
            logger.warning("psycopg2 prune failed: %s — falling back to REST", e)

    # 2순위: Supabase REST (느리지만 대안)
    from ..upsert import get_client
    client = get_client()
    count = _prune_via_rest(client, cutoff, window_days, max_days)
    logger.info("REST prune complete: %d rows deleted (up to %d days processed)", count, max_days)
    return count


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run()
