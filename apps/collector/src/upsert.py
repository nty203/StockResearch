"""Supabase 배치 upsert 공통 유틸."""
from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any

from supabase import create_client, Client

logger = logging.getLogger(__name__)


@contextmanager
def pipeline_run(client: Client, stage: str, github_run_id: str | None = None):
    """Context manager that writes a pipeline_runs row on entry and exit."""
    started_at = datetime.now(timezone.utc).isoformat()
    row_id: str | None = None
    try:
        res = client.table("pipeline_runs").insert({
            "stage": stage,
            "started_at": started_at,
            "status": "running",
            "github_run_id": github_run_id or os.environ.get("GITHUB_RUN_ID"),
        }).execute()
        row_id = (res.data or [{}])[0].get("id")
    except Exception as e:
        logger.warning("pipeline_run insert failed: %s", e)

    rows_processed: list[int] = [0]
    error_msg: list[str | None] = [None]
    try:
        yield rows_processed, error_msg
        status = "success"
    except Exception as exc:
        status = "error"
        error_msg[0] = str(exc)
        raise
    finally:
        if row_id:
            try:
                client.table("pipeline_runs").update({
                    "ended_at": datetime.now(timezone.utc).isoformat(),
                    "status": status,
                    "rows_processed": rows_processed[0] or None,
                    "error_msg": error_msg[0],
                }).eq("id", row_id).execute()
            except Exception as e:
                logger.warning("pipeline_run update failed: %s", e)


def get_client() -> Client:
    """pooler URL 사용 — free tier 직접 연결 제한(5개) 방지."""
    url = os.environ["SUPABASE_URL"]
    key = os.environ.get("SUPABASE_SERVICE_KEY", os.environ.get("SUPABASE_DB_URL", ""))
    return create_client(url, key)


def upsert_batch(
    client: Client,
    table: str,
    rows: list[dict[str, Any]],
    on_conflict: str = "",
    chunk_size: int = 500,
) -> int:
    """rows를 chunk_size 단위로 나눠 upsert. 성공적으로 처리된 행 수 반환."""
    if not rows:
        return 0
    total = 0
    try:
        for i in range(0, len(rows), chunk_size):
            chunk = rows[i : i + chunk_size]
            kwargs: dict[str, Any] = {}
            if on_conflict:
                kwargs["on_conflict"] = on_conflict
            res = client.table(table).upsert(chunk, **kwargs).execute()
            total += len(res.data or chunk)
    except Exception as e:
        logger.warning("upsert_batch error on %s: %s", table, e)
        return 0
    return total
