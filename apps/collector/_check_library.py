"""미분류 라이브러리 종목 상세 정보."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))
if sys.stdout.encoding != 'utf-8':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from dotenv import load_dotenv
load_dotenv()
from supabase import create_client

client = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])

def get_stock_info(ticker):
    stk = client.table("stocks").select("ticker, name_kr, name_en, sector_tag, industry, sector_wics").eq("ticker", ticker).execute()
    if stk.data:
        s = stk.data[0]
        return (s.get("name_kr") or s.get("name_en") or ticker,
                s.get("sector_tag") or "",
                s.get("industry") or "",
                s.get("sector_wics") or "")
    return ticker, "", "", ""

# 미분류 라이브러리 종목 상세
print("[미분류 라이브러리 종목 상세]")
no_cat_tickers = ["000500", "000650", "007810", "017900", "047040", "049630", "187660", "353200", "440110"]
for ticker in no_cat_tickers:
    name, sector, industry, wics = get_stock_info(ticker)
    lib = client.table("hundredx_library_stocks").select(
        "ticker, category, peak_multiplier, notes, pre_rise_signals, triggers"
    ).eq("ticker", ticker).execute()
    if lib.data:
        l = lib.data[0]
        peak = l.get("peak_multiplier") or 0
        signals = l.get("pre_rise_signals") or {}
        triggers = l.get("triggers") or []
        print(f"  {ticker} {name}")
        print(f"       sector_tag={sector!r}  industry={industry!r}  wics={wics!r}")
        print(f"       peak={peak:.1f}x  notes={str(l.get('notes',''))[:100]}")
        if isinstance(signals, dict) and signals:
            print(f"       signals keys: {list(signals.keys())[:10]}")
            # 핵심 신호
            for k in ["categories", "keywords", "trigger_type", "sector"]:
                if k in signals:
                    print(f"         [{k}]: {signals[k]}")
        elif isinstance(signals, list) and signals:
            print(f"       signals[0]: {str(signals[0])[:120]}")
        if triggers:
            print(f"       triggers: {str(triggers[0])[:120]}")
    else:
        print(f"  {ticker} {name} - 라이브러리 없음")
    print()

# 한화엔진 임상_파이프라인 원인: 해당 공시 확인
print("\n[한화엔진(082740) 최근 공시 - 임상 키워드 검색]")
filings_r = client.table("filings").select(
    "ticker, headline, raw_text, filed_at"
).eq("ticker", "082740").order("filed_at", desc=True).limit(5).execute()
clinical_kws = ["CE 인증", "안전성", "유효성", "임상", "FDA", "식약처", "NDA", "BLA", "CDMO"]
for f in (filings_r.data or []):
    text = (f.get("raw_text") or "") + " " + (f.get("headline") or "")
    found_kws = [kw for kw in clinical_kws if kw.lower() in text.lower()]
    if found_kws:
        print(f"  [{f['filed_at'][:10]}] {(f.get('headline') or '')[:80]}")
        print(f"     임상 키워드 히트: {found_kws}")
