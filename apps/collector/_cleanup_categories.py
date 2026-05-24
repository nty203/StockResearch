"""DB 카테고리 중복 정리 — psycopg2 직접 연결 (REST timeout 없음)."""
import os, sys
if sys.stdout.encoding != 'utf-8':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from dotenv import load_dotenv
load_dotenv()

import psycopg2
from datetime import datetime, timezone

db_url = os.environ.get("SUPABASE_DB_URL", "")
if not db_url:
    print("ERROR: SUPABASE_DB_URL not set")
    sys.exit(1)

conn = psycopg2.connect(db_url)
conn.autocommit = True
cur = conn.cursor()

now = datetime.now(timezone.utc).isoformat()

# 정리 전 현황
cur.execute("SELECT COUNT(*) FROM hundredx_category_matches WHERE exited_at IS NULL")
before_total = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM hundredx_category_matches WHERE exited_at IS NULL AND category IN ('미분류', '단기_테마_급등')")
noise_count = cur.fetchone()[0]
print(f"정리 전: 총 활성 {before_total}개 (노이즈 카테고리 {noise_count}개 포함)")

# 1단계: 노이즈 카테고리 종료
cur.execute("""
    UPDATE hundredx_category_matches
    SET exited_at = %s
    WHERE category IN ('미분류', '단기_테마_급등')
      AND exited_at IS NULL
""", (now,))
step1 = cur.rowcount
print(f"1단계: 노이즈 카테고리(미분류/단기_테마_급등) {step1}개 종료")

# 2단계: 동일 종목 비-always-keep 카테고리 중 최고신뢰 1개 외 종료
cur.execute("""
    UPDATE hundredx_category_matches
    SET exited_at = %s
    WHERE exited_at IS NULL
      AND category NOT IN ('임상_파이프라인', '수익성_급전환')
      AND (ticker, category) NOT IN (
        SELECT DISTINCT ON (ticker) ticker, category
        FROM hundredx_category_matches
        WHERE exited_at IS NULL
          AND category NOT IN ('임상_파이프라인', '수익성_급전환')
        ORDER BY ticker, confidence DESC, detected_at DESC
      )
      AND ticker IN (
        SELECT ticker
        FROM hundredx_category_matches
        WHERE exited_at IS NULL
        GROUP BY ticker
        HAVING COUNT(*) > 2
      )
""", (now,))
step2 = cur.rowcount
print(f"2단계: 중복 카테고리 {step2}개 종료")

# 정리 후 현황
cur.execute("SELECT COUNT(*) FROM hundredx_category_matches WHERE exited_at IS NULL")
after_total = cur.fetchone()[0]
print(f"\n정리 후: 총 활성 {after_total}개 (정리 {before_total - after_total}개)")

# 카테고리별 분포
cur.execute("""
    SELECT category, COUNT(*) as cnt, AVG(confidence) as avg_conf
    FROM hundredx_category_matches
    WHERE exited_at IS NULL
    GROUP BY category
    ORDER BY cnt DESC
""")
print("\n카테고리별 분포:")
for row in cur.fetchall():
    print(f"  {row[0]:<25} {row[1]:>3}개  avg_conf={row[2]:.3f}")

# 종목당 카테고리 수 분포
cur.execute("""
    SELECT cnt, COUNT(*) as tickers
    FROM (
        SELECT ticker, COUNT(*) as cnt
        FROM hundredx_category_matches
        WHERE exited_at IS NULL
        GROUP BY ticker
    ) t
    GROUP BY cnt
    ORDER BY cnt
""")
print("\n종목당 카테고리 수 분포:")
for row in cur.fetchall():
    print(f"  {row[0]}개 카테고리: {row[1]}개 종목")

conn.close()
print("\n완료!")
