"""활성 매칭의 first_detected_at을 실제 시그널 발생일로 소급 수정.

시그널 날짜 우선순위:
  1. evidence[].date 중 가장 오래된 날짜 (공시/뉴스 발생일)
  2. 재무 기반 매칭(수익성_급전환/수주잔고_선행): financials 보고일 조회
  3. 위 둘 다 없으면: 현재 값 유지
"""
import os, sys, json
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

# 현재 활성 매칭 전체 조회 (evidence 포함)
cur.execute("""
    SELECT ticker, category, confidence, first_detected_at, evidence
    FROM hundredx_category_matches
    WHERE exited_at IS NULL
    ORDER BY confidence DESC
""")
rows = cur.fetchall()
print(f"활성 매칭 {len(rows)}개 분석\n")

updates = []
no_date = []

for ticker, category, confidence, first_detected_at, evidence_raw in rows:
    evid = evidence_raw or []
    if isinstance(evid, str):
        try:
            evid = json.loads(evid)
        except Exception:
            evid = []

    # evidence에서 날짜 추출
    dates = []
    for e in evid:
        if not isinstance(e, dict):
            continue
        d = e.get("date") or e.get("filed_at") or e.get("report_date")
        if d:
            try:
                dt = str(d)[:10]
                if dt >= "2020-01-01":
                    dates.append(dt)
            except Exception:
                pass

    signal_date = min(dates) if dates else None
    current_fda = str(first_detected_at)[:10] if first_detected_at else None

    if signal_date and signal_date != current_fda:
        updates.append((signal_date + "T00:00:00+00:00", ticker, category, signal_date, current_fda, confidence))
    elif not signal_date:
        no_date.append((ticker, category, confidence))

print(f"소급 업데이트 대상: {len(updates)}개")
for signal_dt, ticker, category, new_date, old_date, conf in updates:
    print(f"  {ticker:<8} {category:<25} {old_date} → {new_date}  (conf={conf:.3f})")

if no_date:
    print(f"\n날짜 없음 (재무기반 등): {len(no_date)}개")
    for ticker, category, conf in no_date:
        print(f"  {ticker:<8} {category:<25} conf={conf:.3f}")

# 적용
print(f"\n{len(updates)}개 소급 적용 중...")
for signal_dt, ticker, category, new_date, old_date, conf in updates:
    cur.execute("""
        UPDATE hundredx_category_matches
        SET first_detected_at = %s
        WHERE ticker = %s AND category = %s AND exited_at IS NULL
    """, (signal_dt, ticker, category))
    print(f"  ✓ {ticker} / {category}: {old_date} → {new_date}")

# 재무기반 매칭 날짜 — financials 테이블에서 조회
if no_date:
    print(f"\n재무기반 매칭 날짜 financials 테이블에서 조회...")
    fin_updates = []
    for ticker, category, conf in no_date:
        cur.execute("""
            SELECT report_date, period_end
            FROM financials
            WHERE ticker = %s
            ORDER BY report_date DESC NULLS LAST, period_end DESC NULLS LAST
            LIMIT 1
        """, (ticker,))
        fin_row = cur.fetchone()
        if fin_row:
            report_date = str(fin_row[0] or fin_row[1] or "")[:10]
            if report_date >= "2020-01-01":
                fin_updates.append((report_date + "T00:00:00+00:00", ticker, category, report_date))
                print(f"  {ticker:<8} {category:<25} → {report_date} (재무보고일)")
            else:
                print(f"  {ticker:<8} {category:<25} → 날짜 없음")
        else:
            print(f"  {ticker:<8} {category:<25} → financials 데이터 없음")

    for signal_dt, ticker, category, new_date in fin_updates:
        cur.execute("""
            UPDATE hundredx_category_matches
            SET first_detected_at = %s
            WHERE ticker = %s AND category = %s AND exited_at IS NULL
        """, (signal_dt, ticker, category))
        print(f"  ✓ {ticker} / {category}: → {new_date}")
    updates.extend(fin_updates)

print(f"\n총 {len(updates)}개 소급 완료.")

# 최종 현황
cur.execute("""
    SELECT ticker, category, confidence, first_detected_at
    FROM hundredx_category_matches
    WHERE exited_at IS NULL
    ORDER BY first_detected_at ASC, confidence DESC
""")
print("\n=== 최종 활성 매칭 (시그널 날짜순) ===")
for r in cur.fetchall():
    fda = str(r[3])[:10] if r[3] else "unknown"
    print(f"  [{fda}] {r[0]:<8} {r[1]:<25} conf={r[2]:.3f}")

conn.close()
