"""PPTR quant-only 가짜 매칭 정리 — 파일링/키워드 증거 없는 항목 전량 종료."""
import os, sys
if sys.stdout.encoding != 'utf-8':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from dotenv import load_dotenv
load_dotenv()

import psycopg2
from datetime import datetime, timezone

db_url = os.environ.get("SUPABASE_DB_URL", "")
conn = psycopg2.connect(db_url)
conn.autocommit = True
cur = conn.cursor()

now = datetime.now(timezone.utc).isoformat()

# 현황 확인
cur.execute("SELECT COUNT(*) FROM hundredx_category_matches WHERE exited_at IS NULL")
before = cur.fetchone()[0]
print(f"정리 전: {before}개 활성")

# quant-only PPTR 매칭 종료
# 조건: evidence가 전부 source_type='quant' 또는 'volume_spike' (filing/keywords 증거 없음)
cur.execute("""
    UPDATE hundredx_category_matches
    SET exited_at = %s
    WHERE exited_at IS NULL
      AND evidence IS NOT NULL
      AND jsonb_array_length(evidence::jsonb) > 0
      AND NOT EXISTS (
        SELECT 1
        FROM jsonb_array_elements(evidence::jsonb) e
        WHERE e->>'source_type' NOT IN ('quant', 'volume_spike')
      )
""", (now,))
quant_exited = cur.rowcount
print(f"퀀트-only PPTR 매칭 종료: {quant_exited}개")

# 정리 후 현황
cur.execute("SELECT COUNT(*) FROM hundredx_category_matches WHERE exited_at IS NULL")
after = cur.fetchone()[0]
print(f"정리 후: {after}개 활성 (정리 {before - after}개)")

# 카테고리별 분포
cur.execute("""
    SELECT category, COUNT(*) as cnt, ROUND(AVG(confidence)::numeric, 3) as avg_conf
    FROM hundredx_category_matches
    WHERE exited_at IS NULL
    GROUP BY category
    ORDER BY cnt DESC
""")
print("\n카테고리별 분포:")
for row in cur.fetchall():
    print(f"  {row[0]:<25} {row[1]:>4}개  avg_conf={row[2]}")

# 상위 종목 (신뢰도 순)
cur.execute("""
    SELECT ticker, category, confidence,
           LEFT(evidence::text, 100) as evid
    FROM hundredx_category_matches
    WHERE exited_at IS NULL
    ORDER BY confidence DESC, detected_at DESC
    LIMIT 20
""")
print("\n상위 20개 (신뢰도 순):")
for row in cur.fetchall():
    print(f"  {row[0]:<8} {row[1]:<25} {row[2]:.3f}")

conn.close()
