"""Supabase PostgREST 1000-row 한계 우회를 위한 페이지네이션 유틸."""
from __future__ import annotations

from typing import Callable, Iterable

PAGE_SIZE = 1000


def fetch_all(query_builder: Callable[[int, int], object]) -> list[dict]:
    """범위 페이지네이션 헬퍼.

    query_builder(start, end) 가 Supabase query (range/limit 미적용)를 리턴해야 한다.
    이 함수가 .range(start, end).execute() 를 직접 호출.

    Example:
        rows = fetch_all(lambda s, e:
            client.table("foo").select("*").eq("active", True).range(s, e)
        )
    """
    out: list[dict] = []
    offset = 0
    while True:
        q = query_builder(offset, offset + PAGE_SIZE - 1)
        res = q.execute()
        data = res.data or []
        out.extend(data)
        if len(data) < PAGE_SIZE:
            break
        offset += PAGE_SIZE
    return out
