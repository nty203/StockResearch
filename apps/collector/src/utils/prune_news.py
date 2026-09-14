"""Prune news and macro_news older than 24 hours.

Run via github actions.
"""
from __future__ import annotations
import logging
import os
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

RETENTION_HOURS = 24


def _prune_via_psycopg2(cutoff: str) -> dict[str, int]:
    """Direct psycopg2 연결로 prune."""
    import psycopg2
    db_url = os.environ.get("SUPABASE_DB_URL", "")
    if not db_url:
        raise RuntimeError("SUPABASE_DB_URL not set")

    conn = psycopg2.connect(db_url)
    conn.autocommit = True
    cur = conn.cursor()

    results = {}
    for table in ["news", "macro_news", "filings"]:
        try:
            # filings 테이블의 컬럼명은 published_at 일지 date 일지 확인이 필요하지만 
            # 보통 created_at이 기본으로 있으므로 created_at 또는 published_at 사용
            # news와 macro_news는 확실히 published_at 이 있음.
            cur.execute(f"DELETE FROM {table} WHERE published_at < %s", (cutoff,))
            deleted = cur.rowcount
            results[table] = deleted
            if deleted > 0:
                logger.info("Pruned %d rows from %s (older than %s)", deleted, table, cutoff)
        except Exception as e:
            logger.warning("Delete failed for %s: %s", table, e)

    conn.close()
    return results


def _prune_via_rest(client, cutoff: str) -> dict[str, int]:
    """Supabase REST client 폴백."""
    results = {}
    for table in ["news", "macro_news", "filings"]:
        try:
            r = (
                client.table(table)
                .delete()
                .lt("published_at", cutoff)
                .execute()
            )
            deleted = len(r.data or [])
            results[table] = deleted
            if deleted > 0:
                logger.info("Pruned %d rows from %s (older than %s)", deleted, table, cutoff)
        except Exception as e:
            logger.warning("REST delete failed for %s: %s", table, e)

    return results


def run() -> dict[str, int]:
    cutoff_dt = datetime.now(timezone.utc) - timedelta(hours=RETENTION_HOURS)
    cutoff = cutoff_dt.isoformat()

    # 1순위: psycopg2 직접 연결 (timeout 없음)
    if os.environ.get("SUPABASE_DB_URL"):
        try:
            results = _prune_via_psycopg2(cutoff)
            logger.info("psycopg2 prune complete: %s", results)
            return results
        except Exception as e:
            logger.warning("psycopg2 prune failed: %s — falling back to REST", e)

    # 2순위: Supabase REST
    from ..upsert import get_client
    client = get_client()
    results = _prune_via_rest(client, cutoff)
    logger.info("REST prune complete: %s", results)
    return results


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    logging.basicConfig(level=logging.INFO)
    run()
