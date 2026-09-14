"""pptr_rule_matches / pptr_rule_near_misses 중복 행 제거.

(rule_id, ticker) 조합별 matched_at/detected_at 가장 최신 1건만 남기고 나머지 삭제.
scanner.py insert->upsert 전환 전 누적된 중복행 정리용 1회성 스크립트.
"""
from __future__ import annotations
import os, sys, io
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from dotenv import load_dotenv
load_dotenv()
from supabase import create_client

client = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])


def dedup_table(table: str, date_col: str) -> dict:
    """(rule_id, ticker) 조합별 최신 1건만 남기고 나머지 id 삭제."""
    all_rows = client.table(table).select(f"id, rule_id, ticker, {date_col}").execute()
    rows = all_rows.data or []
    print(f"\n[{table}] 전체 {len(rows)}행")

    # group by (rule_id, ticker) → keep max date, collect others
    from collections import defaultdict
    groups: dict[tuple, list] = defaultdict(list)
    for r in rows:
        key = (r["rule_id"], r["ticker"])
        groups[key].append(r)

    to_delete: list[int] = []
    for key, group in groups.items():
        if len(group) <= 1:
            continue
        # sort by date desc → keep first, delete rest
        group.sort(key=lambda x: x.get(date_col) or "", reverse=True)
        for old in group[1:]:
            to_delete.append(old["id"])

    print(f"  삭제 대상: {len(to_delete)}행")
    if not to_delete:
        return {"deleted": 0}

    deleted = 0
    chunk_size = 100
    for i in range(0, len(to_delete), chunk_size):
        chunk = to_delete[i:i + chunk_size]
        try:
            client.table(table).delete().in_("id", chunk).execute()
            deleted += len(chunk)
        except Exception as e:
            print(f"  ⚠ delete error chunk {i}: {e}")

    print(f"  ✅ 삭제 완료: {deleted}행")
    return {"deleted": deleted}


r1 = dedup_table("pptr_rule_matches", "matched_at")
r2 = dedup_table("pptr_rule_near_misses", "detected_at")
print(f"\n=== 완료 === matches -{r1['deleted']}행, near_misses -{r2['deleted']}행")
