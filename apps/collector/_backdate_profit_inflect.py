"""수익성_급전환 매칭의 first_detected_at을 재무 시그널 분기로 소급."""
import os, sys
if sys.stdout.encoding != 'utf-8':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from dotenv import load_dotenv
load_dotenv()
import psycopg2

# fq "2024Q1" → 한국 DART 공시 기준 대략적 보고일
FQ_REPORT_MONTH = {"Q1": "05-15", "Q2": "08-14", "Q3": "11-14", "Q4": "03-31"}

def fq_to_report_date(fq: str) -> str | None:
    """예: "2024Q3" → "2024-11-14" (분기보고서 제출 기준일)"""
    try:
        year = fq[:4]
        q = fq[4:]  # "Q1"
        month_day = FQ_REPORT_MONTH.get(q)
        if not month_day:
            return None
        # Q4는 다음 해 3월
        if q == "Q4":
            return f"{int(year)+1}-{month_day}"
        return f"{year}-{month_day}"
    except Exception:
        return None

conn = psycopg2.connect(os.environ['SUPABASE_DB_URL'])
conn.autocommit = True
cur = conn.cursor()

cur.execute("""
    SELECT ticker, category, confidence, first_detected_at
    FROM hundredx_category_matches
    WHERE exited_at IS NULL AND category = '수익성_급전환'
    ORDER BY confidence DESC
""")
rows = cur.fetchall()

for ticker, category, confidence, fda in rows:
    # 흑자전환 시점 탐색: op_income이 양수 전환된 첫 분기
    cur.execute("""
        SELECT fq, op_income, op_margin
        FROM financials_q
        WHERE ticker = %s AND op_income IS NOT NULL
        ORDER BY fq ASC
    """, (ticker,))
    quarters = cur.fetchall()

    signal_fq = None
    if len(quarters) >= 2:
        for i in range(1, len(quarters)):
            curr_op = float(quarters[i][1] or 0)
            prev_op = float(quarters[i-1][1] or 0)
            if curr_op > 0 and prev_op <= 0:
                signal_fq = quarters[i][0]
                print(f"  {ticker}: 흑자전환 {signal_fq} (op={curr_op/1e8:.0f}억 ← {prev_op/1e8:.0f}억)")
                break

    # 흑자전환 없으면: op_margin이 가장 크게 개선된 분기
    if not signal_fq and len(quarters) >= 2:
        best_delta = 0
        best_fq = None
        for i in range(1, len(quarters)):
            curr_opm = float(quarters[i][2] or 0)
            prev_opm = float(quarters[i-1][2] or 0)
            delta = curr_opm - prev_opm
            if delta > best_delta:
                best_delta = delta
                best_fq = quarters[i][0]
        if best_fq and best_delta >= 3.0:  # 3%p 이상 개선
            signal_fq = best_fq
            print(f"  {ticker}: OPM 최대 개선 {signal_fq} (+{best_delta:.1f}%p)")

    # 그래도 없으면 가장 최근 분기
    if not signal_fq and quarters:
        signal_fq = quarters[-1][0]
        print(f"  {ticker}: 최근 분기 사용 {signal_fq}")

    signal_date = fq_to_report_date(signal_fq) if signal_fq else None
    current_fda = str(fda)[:10] if fda else None

    if signal_date and signal_date != current_fda:
        cur.execute("""
            UPDATE hundredx_category_matches
            SET first_detected_at = %s
            WHERE ticker = %s AND category = %s AND exited_at IS NULL
        """, (signal_date + "T00:00:00+00:00", ticker, category))
        print(f"    ✓ {ticker} / {category}: {current_fda} → {signal_date} (분기: {signal_fq})")
    else:
        print(f"    → {ticker}: 소급 불필요 (현재 {current_fda})")

# 최종 결과
print()
cur.execute("""
    SELECT first_detected_at::date as sig_date, ticker, category, confidence
    FROM hundredx_category_matches
    WHERE exited_at IS NULL
    ORDER BY first_detected_at ASC, confidence DESC
""")
print("=== 최종 활성 매칭 (시그널 날짜순) ===")
for r in cur.fetchall():
    print(f"  [{r[0]}] {r[1]:<8} {r[2]:<25} conf={r[3]:.3f}")

conn.close()
