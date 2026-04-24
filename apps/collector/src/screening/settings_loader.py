"""Supabase settings 테이블에서 설정을 fetch하는 공통 유틸.

Usage:
    from apps.collector.src.screening.settings_loader import load_settings
    cfg = load_settings(supabase_client)
    threshold = cfg.get("enqueue_score_threshold", 65)
"""
from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


def load_settings(client) -> dict[str, Any]:
    """settings 테이블 전체를 key→value dict로 반환."""
    try:
        result = client.table("settings").select("key, value_json").execute()
        rows = result.data or []
    except Exception as e:
        logger.warning("Failed to load settings: %s", e)
        return {}

    cfg: dict[str, Any] = {}
    for row in rows:
        val = row["value_json"]
        # JSONB에서 반환된 값이 문자열이면 파싱
        if isinstance(val, str):
            try:
                val = json.loads(val)
            except json.JSONDecodeError:
                pass
        cfg[row["key"]] = val
    return cfg
