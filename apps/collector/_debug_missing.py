"""Why are 000150, 005930, 000660 not detected?"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))
if sys.stdout.encoding != 'utf-8':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from dotenv import load_dotenv
load_dotenv()
from supabase import create_client
from datetime import date, timedelta

client = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])

from src.hundredx.categories.bigtech_partner import detect as detect_bigtech
from src.hundredx.categories.clinical_pipe   import detect as detect_clinical
from src.hundredx.categories.supply_choke    import detect as detect_supply
from src.hundredx.categories.policy_benefit  import detect as detect_policy
from src.hundredx.categories.backlog_lead    import detect as detect_backlog
from src.hundredx.categories.profit_inflect  import detect as detect_profit
from src.hundredx.categories.platform_mono   import detect as detect_mono
from src.utils.db_fetch import bulk_fetch_financials

TARGETS = [
    ("000150", "두산에너빌리티", "정책_수혜/원전"),
    ("005930", "삼성전자", "빅테크_파트너/HBM"),
    ("000660", "SK하이닉스", "빅테크_파트너/HBM"),
]

DETECTORS = [
    ("빅테크_파트너", detect_bigtech),
    ("임상_파이프라인", detect_clinical),
    ("공급_병목", detect_supply),
    ("정책_수혜", detect_policy),
    ("수주잔고_선행", detect_backlog),
    ("수익성_급전환", detect_profit),
    ("플랫폼_독점", detect_mono),
]

tickers = [t for t, _, _ in TARGETS]
fin_data = bulk_fetch_financials(client, tickers)
stocks_res = client.table("stocks").select("ticker, market, sector_tag").in_("ticker", tickers).execute()
sector_by_ticker = {r["ticker"]: r.get("sector_tag") or "" for r in (stocks_res.data or [])}

cutoff = (date.today() - timedelta(days=90)).isoformat()

print("=" * 70)
print("미탐지 종목 상세 디버그")
print("=" * 70)

for ticker, name, expected in TARGETS:
    print(f"\n--- {ticker} {name} (기대: {expected}) ---")

    # Fetch filings
    res = (
        client.table("filings")
        .select("ticker, headline, raw_text, filed_at, source")
        .eq("ticker", ticker)
        .gte("filed_at", cutoff)
        .order("filed_at", desc=True)
        .limit(10)
        .execute()
    )
    filings = res.data or []
    print(f"  공시 수: {len(filings)}")
    for f in filings:
        print(f"  [{f['filed_at'][:10]}] {f.get('source','?'):<6} {(f.get('headline') or '')[:70]}")

    if not filings:
        print("  → 공시 없음 (filings table에 seed가 없거나 날짜 범위 벗어남)")
        # Check if seed filing exists
        all_res = client.table("filings").select("*").eq("ticker", ticker).execute()
        print(f"  전체 공시(날짜 무관): {len(all_res.data or [])}개")
        for f in (all_res.data or []):
            print(f"    [{f['filed_at'][:10]}] {(f.get('headline') or '')[:60]}")
        continue

    # Run detectors
    stock_data = fin_data.get(ticker, {"ticker": ticker})
    stock_data["ticker"] = ticker
    stock_data["sector_tag"] = sector_by_ticker.get(ticker, "")
    print(f"  섹터: {stock_data['sector_tag']}")

    for cat, detector_fn in DETECTORS:
        try:
            m = detector_fn(stock_data, filings)
            if m:
                status = "✅" if m.confidence >= 0.70 else "⚠️ (낮음)"
                print(f"  {status} {cat:<20} conf={m.confidence:.3f}")
            else:
                print(f"  ❌ {cat:<20} None")
        except Exception as e:
            print(f"  💥 {cat:<20} Error: {e}")
