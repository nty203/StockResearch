"""실제 DB 데이터로 누락 library 종목들의 탐지 가능 여부 즉시 검증.

실제 filings 테이블에서 해당 종목의 최근 공시를 가져와 각 detector를 실행.
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))
if sys.stdout.encoding != 'utf-8':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

from dotenv import load_dotenv
load_dotenv()
from supabase import create_client

url = os.environ["SUPABASE_URL"]
key = os.environ["SUPABASE_SERVICE_KEY"]
client = create_client(url, key)

import logging
logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")

from src.hundredx.categories.bigtech_partner import detect as detect_bigtech
from src.hundredx.categories.clinical_pipe   import detect as detect_clinical
from src.hundredx.categories.supply_choke    import detect as detect_supply
from src.hundredx.categories.policy_benefit  import detect as detect_policy
from src.hundredx.categories.backlog_lead    import detect as detect_backlog
from src.hundredx.categories.profit_inflect  import detect as detect_profit
from src.hundredx.categories.platform_mono   import detect as detect_mono
from src.utils.db_fetch                   import bulk_fetch_financials

MIN_CONF = 0.70

# 탐지 누락 library 종목 (검증 대상)
MISSED_TARGETS = [
    # (ticker, library_category, peak_x)
    ("277810", "빅테크_파트너", 20.0),   # 레인보우로보틱스
    ("007660", "빅테크_파트너", 54.0),   # 이수페타시스
    ("087010", "임상_파이프라인", 41.0), # 펩트론
    ("000250", "임상_파이프라인", None), # 삼천당제약
    ("042700", "공급_병목", 15.0),       # 한일진공/한국카본?
    ("298040", "수주잔고_선행", 18.0),
    ("032820", "수주잔고_선행", 16.2),
    ("108490", "빅테크_파트너", 13.1),   # 로보티즈
    ("001570", "이차전지_소재", 36.9),
    ("005930", "플랫폼_독점", 1.6),      # 삼성전자
    ("000150", "지주사_재평가", 3.5),
    ("010140", "조선_슈퍼사이클", 2.0),
    ("000660", "빅테크_파트너", 3.3),    # SK하이닉스
]

DETECTORS = [
    ("빅테크_파트너",   detect_bigtech),
    ("임상_파이프라인", detect_clinical),
    ("공급_병목",       detect_supply),
    ("정책_수혜",       detect_policy),
    ("수주잔고_선행",   detect_backlog),
    ("수익성_급전환",   detect_profit),
    ("플랫폼_독점",     detect_mono),
]

print("\n" + "="*70)
print("실제 DB filings 기반 누락 종목 탐지 검증")
print("="*70)

# Bulk-fetch financials for all target tickers
tickers = [t for t, _, _ in MISSED_TARGETS]
fin_data = bulk_fetch_financials(client, tickers)

# Fetch stocks for sector_tag
stocks_res = client.table("stocks").select("ticker, market, sector_tag").in_("ticker", tickers).execute()
sector_by_ticker = {r["ticker"]: r.get("sector_tag") or "" for r in (stocks_res.data or [])}
market_by_ticker = {r["ticker"]: r.get("market") or "" for r in (stocks_res.data or [])}

# Fetch recent filings (2년치) for each ticker
from datetime import date, timedelta
cutoff_90d = (date.today() - timedelta(days=90)).isoformat()
cutoff_2y  = (date.today() - timedelta(days=730)).isoformat()

def fetch_filings(ticker, days=730):
    cutoff = (date.today() - timedelta(days=days)).isoformat()
    res = (
        client.table("filings")
        .select("id, ticker, headline, raw_text, filed_at")
        .eq("ticker", ticker)
        .gte("filed_at", cutoff)
        .order("filed_at", desc=True)
        .limit(20)
        .execute()
    )
    return res.data or []

results = []
for ticker, lib_cat, peak_x in MISSED_TARGETS:
    filings_2y  = fetch_filings(ticker, 730)
    filings_90d = [f for f in filings_2y if f["filed_at"][:10] >= cutoff_90d]

    stock_data = fin_data.get(ticker, {"ticker": ticker})
    stock_data["ticker"] = ticker
    stock_data["sector_tag"] = sector_by_ticker.get(ticker, "")

    detected = []
    for cat, detector_fn in DETECTORS:
        f = filings_2y if cat == "임상_파이프라인" else filings_90d
        try:
            m = detector_fn(stock_data, f)
            if m and m.confidence >= MIN_CONF:
                detected.append((cat, m.confidence))
        except Exception as e:
            pass

    n_filings = len(filings_2y)
    n_filings_90 = len(filings_90d)
    peak_str = f"{peak_x:.0f}x" if peak_x else "?"

    if detected:
        best_cat, best_conf = max(detected, key=lambda x: x[1])
        status = f"DETECTED [{best_cat} conf={best_conf:.3f}]"
        if any(c == lib_cat for c, _ in detected):
            status = f"✅ MATCH   [{best_cat} conf={best_conf:.3f}]"
        else:
            status = f"⚠️  WRONG  [{best_cat} conf={best_conf:.3f}] (expect {lib_cat})"
    else:
        status = f"❌ MISS    (expect {lib_cat})"

    results.append((ticker, lib_cat, peak_str, n_filings, n_filings_90, status))
    print(f"  {ticker:<10} {lib_cat:<20} {peak_str:>5}  {n_filings_90:>3}d90/{n_filings:>3}d2y  {status}")

# Summary
detected_ok = sum(1 for *_, s in results if "MATCH" in s or "DETECTED" in s)
total = len(results)
print(f"\n탐지 결과: {detected_ok}/{total} ({detected_ok/total:.0%})")

# Show filings for missed stocks
missed = [(t, c, n90, n2y) for t, c, *_, n90, n2y, s in
          [(r[0], r[1], r[3], r[4], r[5]) for r in results]
          if "MISS" in [(r[0], r[1], r[3], r[4], r[5]) for r in results if r[0] == t][0][4]]

print("\n[누락 종목 최근 공시 미리보기]")
for ticker, lib_cat, peak_str, n90, n2y, status in results:
    if "MISS" not in status:
        continue
    filings = fetch_filings(ticker, 730)
    print(f"\n  {ticker} ({lib_cat} {peak_str}) -- {n2y}개 공시 (최근 90일: {n90}개)")
    for f in filings[:3]:
        print(f"    [{f['filed_at'][:10]}] {(f.get('headline') or '')[:80]}")
    if not filings:
        print("    (공시 없음 -- DB에 데이터 없음)")
