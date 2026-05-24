"""
Data source investigation for historical Korean stock financial data.
Tests: FinanceDataReader, pykrx, Naver Finance scraping, KRX/KIND, yfinance, DART
Target: historical financials (revenue, op_income, op_margin) for 2020-2023
Test tickers:
  042700 - 한미반도체 (rise ~2023-01)
  000660 - SK하이닉스
  298040 - 효성중공업 (rise ~2022-10)

=== FINDINGS SUMMARY (2026-05-24) ===

1. yfinance (Yahoo Finance) - BEST SOURCE for recent data
   - Works for all .KS (KOSPI) and .KQ (KOSDAQ) stocks
   - Provides: income_stmt (annual), quarterly_income_stmt
   - Available rows: Total Revenue, Operating Income, Gross Profit, EBIT, etc.
   - Annual data: FY2022, FY2023, FY2024, FY2025 (4 years, with 2021 NaN)
   - Quarterly data: last 7 quarters only (~2025)
   - Coverage for pre_rise_signals (18mo before rise):
     * 2025-2026 rises: COVERED (need 2024+, have 2022+)
     * 2024 rises: COVERED (need 2022+, have 2022+)
     * 2023 rises: PARTIAL (need Jul2021+, have 2022 annual) - FY2022 data exists!
     * 2022 rises: MISSING (need 2020-2021 data)
     * 2021-and-earlier: MISSING (need 2018-2020 data)
   - NOTE: revenue/op_income values are in KRW (raw won, not millions)

2. FinanceDataReader (FDR) - PRICE DATA ONLY
   - Works for Korean stock prices going back to 2015+
   - NO financial statement data (revenue, op_income, etc.)
   - StockListing gives: Code, Name, Market, Close, Marcap, etc.
   - NO income statement or balance sheet data

3. pykrx - BROKEN (requires KRX login since 2024)
   - get_market_fundamental_by_date() returns empty for ALL dates
   - KRX changed auth requirements; KRX_ID/KRX_PW env vars required
   - Would have provided: PER, PBR, EPS, DIV, DPS - but NOT income statement
   - NOT useful without KRX credentials

4. DART disclosure scraping (no API key) - WORKS for filing HEADLINES
   - URL: https://dart.fss.or.kr/dsab001/search.ax
   - Search by company name (textCrpNm), date range
   - Returns: title, date, rcpNo (rceipt number for full report)
   - Goes back to 2010+ (very deep historical coverage)
   - Encoding: UTF-8 (DART server sends UTF-8)
   - Example result: {'title': '단일판매ㆍ공급계약체결(자율공시)', 'date': '2019.11.14', 'rcpt_no': '20191114002480'}
   - Limitation: Search by company NAME, not ticker code directly
     (ticker code search via repIsuSrtCd doesn't work reliably)
   - DART API (JSON) requires API key - HTML scraping is the fallback

5. Naver Finance / WiseReport / FnGuide - LIMITED
   - FnGuide: only shows 2022-2025 annual data (4 years)
   - WiseReport: only shows 2025-2026 recent data
   - Naver Finance main page: stock info but no historical financials accessible
   - None of these have accessible 2018-2021 data without JS execution

6. KRX data portal (data.krx.co.kr) - REQUIRES SESSION AUTH
   - All endpoints return '400 LOGOUT' without proper session
   - Would need cookie-based session (complex to automate)

=== DATA GAP ANALYSIS FOR LIBRARY STOCKS ===
- 13 stocks (2024-2026 rises): yfinance COVERS pre-rise period fully
- 16 stocks (2023 rises): yfinance HAS FY2022 annual data (covers 12/18 months)
- 20 stocks (pre-2023 rises): yfinance MISSING pre-rise financial data
  * These need 2018-2021 data - no programmatic source found without DART API key

=== RECOMMENDATION ===
Priority 1: Use yfinance for 2023+ rises (29 stocks)
  - Fetch: tk = yf.Ticker(f'{ticker}.KQ'); tk.income_stmt
  - Units in KRW (divide by 1e8 for 억원, 1e12 for 조원)

Priority 2: DART HTML scraping for filing headlines (all date ranges)
  - Can get disclosure titles for 2015+ for all stocks
  - Useful for keyword pattern matching (e.g., 수주, 임상, 계약 titles)

Priority 3: For stocks rising 2020-2022 (20 stocks needing 2018-2021 data):
  - DART API key would unlock DART OpenAPI with financial statements
  - Alternative: Consider manual entry / low priority for pre-2022 stocks
"""

import sys
import json
import time
import traceback
from datetime import datetime

TICKERS = ["042700", "000660", "298040"]

# ─────────────────────────────────────────────────────────────────
# 1. FinanceDataReader
# ─────────────────────────────────────────────────────────────────
def test_fdr():
    print("\n" + "="*60)
    print("1. FinanceDataReader")
    print("="*60)
    import FinanceDataReader as fdr

    for ticker in TICKERS:
        print(f"\n--- {ticker} ---")

        # Try various endpoint patterns documented / commonly known
        endpoints = [
            f"{ticker}/annual",
            f"{ticker}/finance",
            f"KRX:{ticker}",
        ]

        for ep in endpoints:
            try:
                df = fdr.DataReader(ep)
                print(f"  fdr.DataReader('{ep}') → shape={df.shape}, cols={list(df.columns)[:8]}")
                if not df.empty:
                    print(f"    index range: {df.index[0]} … {df.index[-1]}")
                    print(df.head(3).to_string())
            except Exception as e:
                print(f"  fdr.DataReader('{ep}') → ERROR: {e}")

        # Try StockListing for financial info
        try:
            info = fdr.StockListing('KRX')
            row = info[info['Code'] == ticker]
            if not row.empty:
                print(f"  StockListing row: {row.iloc[0].to_dict()}")
        except Exception as e:
            print(f"  StockListing → ERROR: {e}")

    # Try the SnapShot / financial statement readers
    print("\n--- Trying fdr financial statement readers ---")
    for fn_name in ['DataReader']:
        for ep in ['FSS:042700', 'KRXFIN:042700', '042700/fs', '042700/income']:
            try:
                df = fdr.DataReader(ep)
                print(f"  fdr.DataReader('{ep}') → shape={df.shape}")
                print(df.head(3).to_string())
            except Exception as e:
                print(f"  fdr.DataReader('{ep}') → {type(e).__name__}: {str(e)[:100]}")


# ─────────────────────────────────────────────────────────────────
# 2. pykrx
# ─────────────────────────────────────────────────────────────────
def test_pykrx():
    print("\n" + "="*60)
    print("2. pykrx")
    print("="*60)
    try:
        from pykrx import stock
    except ImportError:
        print("  pykrx not installed")
        return

    for ticker in TICKERS:
        print(f"\n--- {ticker} ---")

        # Fundamental data (PER, PBR, etc.) for a historical date
        test_dates = ["20220101", "20210101", "20200101"]
        for dt in test_dates:
            try:
                df = stock.get_market_fundamental_by_date(
                    fromdate=dt, todate=dt, ticker=ticker
                )
                if not df.empty:
                    print(f"  fundamental {dt}: {df.iloc[0].to_dict()}")
                else:
                    print(f"  fundamental {dt}: empty")
            except Exception as e:
                print(f"  fundamental {dt}: ERROR {e}")
            time.sleep(0.3)

        # Annual financial statements via pykrx
        try:
            df = stock.get_market_cap_by_date("20200101", "20230101", ticker)
            if not df.empty:
                print(f"  market_cap shape={df.shape}, cols={list(df.columns)}")
                print(df.tail(3).to_string())
        except Exception as e:
            print(f"  market_cap: ERROR {e}")
        time.sleep(0.3)

    # pykrx financial statements
    print("\n--- pykrx financial statement functions ---")
    for fn in ['get_market_fundamental', 'get_index_fundamental']:
        if hasattr(stock, fn):
            print(f"  stock.{fn} exists")
        else:
            print(f"  stock.{fn} NOT FOUND")

    # Check available functions
    fns = [x for x in dir(stock) if 'financ' in x.lower() or 'income' in x.lower()
           or 'balance' in x.lower() or 'profit' in x.lower() or 'revenue' in x.lower()]
    print(f"  Finance-related functions: {fns}")


# ─────────────────────────────────────────────────────────────────
# 3. Naver Finance scraping
# ─────────────────────────────────────────────────────────────────
def test_naver_finance():
    print("\n" + "="*60)
    print("3. Naver Finance scraping")
    print("="*60)
    import requests
    from bs4 import BeautifulSoup

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept-Language": "ko-KR,ko;q=0.9",
    }

    for ticker in TICKERS[:2]:  # test 2 tickers
        print(f"\n--- {ticker} ---")

        # 1) Main page - check what's there
        url = f"https://finance.naver.com/item/main.naver?code={ticker}"
        try:
            r = requests.get(url, headers=headers, timeout=10)
            soup = BeautifulSoup(r.text, 'html.parser')

            # Find financial summary table
            tables = soup.find_all('table')
            print(f"  main page: {len(tables)} tables found")
            for i, t in enumerate(tables[:5]):
                rows = t.find_all('tr')
                if rows:
                    first_row = rows[0].get_text(strip=True)[:80]
                    print(f"    table[{i}]: {len(rows)} rows, first='{first_row}'")
        except Exception as e:
            print(f"  main page ERROR: {e}")
        time.sleep(0.5)

        # 2) Financial info page (coinfo) - has quarterly/annual data
        url2 = f"https://finance.naver.com/item/coinfo.naver?code={ticker}"
        try:
            r2 = requests.get(url2, headers=headers, timeout=10)
            soup2 = BeautifulSoup(r2.text, 'html.parser')
            tables2 = soup2.find_all('table')
            print(f"  coinfo page: {len(tables2)} tables")
            for i, t in enumerate(tables2[:5]):
                rows = t.find_all('tr')
                if len(rows) > 2:
                    header = rows[0].get_text(strip=True)[:100]
                    print(f"    table[{i}]: {len(rows)} rows, header='{header}'")
        except Exception as e:
            print(f"  coinfo page ERROR: {e}")
        time.sleep(0.5)

        # 3) Financial statement iframe (where real data lives)
        url3 = f"https://finance.naver.com/item/financialSummary.naver?code={ticker}"
        try:
            r3 = requests.get(url3, headers=headers, timeout=10)
            soup3 = BeautifulSoup(r3.text, 'html.parser')
            # Look for revenue/operating profit rows
            text = soup3.get_text()
            lines = [l.strip() for l in text.split('\n') if l.strip() and len(l.strip()) > 3]
            print(f"  financialSummary: {len(lines)} non-empty lines")
            for l in lines[:30]:
                print(f"    {l}")
        except Exception as e:
            print(f"  financialSummary ERROR: {e}")
        time.sleep(0.5)

        # 4) Try the API-style endpoint used by Naver's chart
        url4 = f"https://api.finance.naver.com/service/itemSummary.nhn?itemcode={ticker}"
        try:
            r4 = requests.get(url4, headers=headers, timeout=10)
            data = r4.json()
            print(f"  itemSummary API: {list(data.keys())[:10]}")
        except Exception as e:
            print(f"  itemSummary API ERROR: {e}")
        time.sleep(0.5)


# ─────────────────────────────────────────────────────────────────
# 3b. Naver Finance - deep financial statement scrape
# ─────────────────────────────────────────────────────────────────
def test_naver_finance_deep():
    print("\n" + "="*60)
    print("3b. Naver Finance - deep financial statements")
    print("="*60)
    import requests
    from bs4 import BeautifulSoup

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept-Language": "ko-KR,ko;q=0.9",
        "Referer": "https://finance.naver.com/",
    }

    ticker = "042700"  # 한미반도체
    print(f"\nTicker: {ticker} (한미반도체)")

    # The financial data is embedded in an iframe at:
    # https://navercomp.wisereport.co.kr/v2/company/c1010001.aspx?cmp_cd=042700
    wisereport_url = f"https://navercomp.wisereport.co.kr/v2/company/c1010001.aspx?cmp_cd={ticker}"
    try:
        r = requests.get(wisereport_url, headers=headers, timeout=15)
        soup = BeautifulSoup(r.text, 'html.parser')
        print(f"  WiseReport status: {r.status_code}, len={len(r.text)}")
        # Look for financial tables
        tables = soup.find_all('table', class_=lambda c: c and 'pf' in c.lower())
        print(f"  pf-tables: {len(tables)}")
        all_tables = soup.find_all('table')
        print(f"  all tables: {len(all_tables)}")
        if all_tables:
            for t in all_tables[:3]:
                rows = t.find_all('tr')
                print(f"    table ({len(rows)} rows):")
                for row in rows[:5]:
                    cells = [c.get_text(strip=True) for c in row.find_all(['td', 'th'])]
                    if cells:
                        print(f"      {cells[:8]}")
    except Exception as e:
        print(f"  WiseReport ERROR: {e}")
    time.sleep(1)

    # Try FnGuide embed (another source Naver uses)
    fnguide_url = f"https://comp.fnguide.com/SVO2/ASP/SVD_Main.asp?pGB=1&gicode=A{ticker}"
    try:
        r2 = requests.get(fnguide_url, headers=headers, timeout=15)
        soup2 = BeautifulSoup(r2.text, 'html.parser')
        print(f"\n  FnGuide status: {r2.status_code}, len={len(r2.text)}")
        # Find income statement section
        tables = soup2.find_all('table')
        print(f"  tables: {len(tables)}")
        for t in tables[:5]:
            rows = t.find_all('tr')
            if len(rows) > 3:
                print(f"  table ({len(rows)} rows):")
                for row in rows[:6]:
                    cells = [c.get_text(strip=True) for c in row.find_all(['td', 'th'])]
                    if any(c for c in cells):
                        print(f"    {cells[:8]}")
    except Exception as e:
        print(f"  FnGuide ERROR: {e}")
    time.sleep(1)


# ─────────────────────────────────────────────────────────────────
# 4. KRX / KIND disclosure search
# ─────────────────────────────────────────────────────────────────
def test_krx_kind():
    print("\n" + "="*60)
    print("4. KRX / KIND disclosure headlines")
    print("="*60)
    import requests

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json, text/javascript, */*",
        "Referer": "https://kind.krx.co.kr/",
    }

    ticker = "042700"

    # KIND AJAX endpoint for disclosures
    url = "https://kind.krx.co.kr/disclosure/searcher.do"
    params = {
        "method": "searchDisclosureSub",
        "currentPageSize": "20",
        "pageIndex": "1",
        "orderMode": "1",
        "orderStat": "D",
        "forward": "searcher_sub",
        "chose": "S",
        "stock_cd": ticker,
        "fromData": "2021-01-01",
        "toData": "2022-12-31",
        "repIsuSrtCd": ticker,
    }
    try:
        r = requests.get(url, params=params, headers=headers, timeout=15)
        print(f"  KIND searcher status: {r.status_code}, len={len(r.text)}")
        print(f"  Content-Type: {r.headers.get('Content-Type', '')}")
        if r.status_code == 200:
            try:
                data = r.json()
                print(f"  JSON keys: {list(data.keys())}")
                if 'result' in data:
                    items = data['result']
                    print(f"  {len(items)} disclosures")
                    for item in items[:5]:
                        print(f"    {item}")
            except:
                print(f"  Not JSON. First 500 chars: {r.text[:500]}")
    except Exception as e:
        print(f"  KIND searcher ERROR: {e}")
    time.sleep(1)

    # Try KRX OPEN API for financial data
    krx_url = "https://data.krx.co.kr/comm/bldAttendant/getJsonData.cmd"
    krx_params = {
        "bld": "dbms/MDC/STAT/standard/MDCSTAT03901",
        "locale": "ko_KR",
        "trdDd": "20220101",
        "strtIsuCd": ticker,
        "share": "1",
        "money": "1",
        "csvxls_isNo": "false",
    }
    try:
        r2 = requests.get(krx_url, params=krx_params, headers=headers, timeout=15)
        print(f"\n  KRX financial data status: {r2.status_code}")
        if r2.status_code == 200:
            try:
                data2 = r2.json()
                print(f"  JSON keys: {list(data2.keys())}")
                if 'OutBlock_1' in data2:
                    print(f"  OutBlock_1[0]: {data2['OutBlock_1'][0]}")
            except:
                print(f"  Not JSON. First 300: {r2.text[:300]}")
    except Exception as e:
        print(f"  KRX financial ERROR: {e}")
    time.sleep(1)


# ─────────────────────────────────────────────────────────────────
# 5. FinanceDataReader - detailed investigation
# ─────────────────────────────────────────────────────────────────
def test_fdr_detailed():
    print("\n" + "="*60)
    print("5. FinanceDataReader - detailed investigation")
    print("="*60)
    import FinanceDataReader as fdr

    ticker = "042700"

    # Check all available DataReader sources
    print("Checking FDR source patterns for Korean financials:")

    patterns = [
        f"KRX/{ticker}",
        f"NAVER/{ticker}",
        f"{ticker}",  # price only - check columns
    ]

    for p in patterns:
        try:
            df = fdr.DataReader(p, start="2020-01-01", end="2023-12-31")
            print(f"\n  DataReader('{p}', 2020-2023):")
            print(f"    shape={df.shape}, cols={list(df.columns)}")
            if not df.empty:
                print(f"    index: {df.index[0]} … {df.index[-1]}")
                print(df.head(3).to_string())
        except Exception as e:
            print(f"  DataReader('{p}') ERROR: {type(e).__name__}: {str(e)[:120]}")

    # FDR has a StockListing function - check if financials are embedded
    try:
        listing = fdr.StockListing('KRX')
        print(f"\n  KRX listing cols: {list(listing.columns)}")
        row = listing[listing['Code'] == ticker]
        if not row.empty:
            print(f"  Row for {ticker}: {row.iloc[0].to_dict()}")
    except Exception as e:
        print(f"  StockListing ERROR: {e}")

    # Check if FDR has a financials module
    try:
        import FinanceDataReader.data as fdr_data
        print(f"\n  fdr_data attrs: {[x for x in dir(fdr_data) if not x.startswith('_')][:20]}")
    except Exception as e:
        print(f"  fdr.data ERROR: {e}")

    # Try the snapshots endpoint
    try:
        snap = fdr.DataReader("KRX:INC:042700")
        print(f"\n  KRX:INC snap: {snap.shape}")
    except Exception as e:
        print(f"  KRX:INC ERROR: {str(e)[:100]}")


# ─────────────────────────────────────────────────────────────────
# 6. OpenDartReader (DART without API key - check public endpoints)
# ─────────────────────────────────────────────────────────────────
def test_dart_public():
    print("\n" + "="*60)
    print("6. DART public endpoints (no API key)")
    print("="*60)
    import requests

    headers = {"User-Agent": "Mozilla/5.0"}

    # DART has some public JSON endpoints
    # Try company search
    corp_code = "00164779"  # 한미반도체 corp code (known)
    ticker = "042700"

    # Public disclosure list
    url = f"https://dart.fss.or.kr/api/search.json?corp_code={corp_code}&start_dt=20210101&end_dt=20221231"
    try:
        r = requests.get(url, headers=headers, timeout=15)
        print(f"  DART search status: {r.status_code}")
        if r.status_code == 200:
            data = r.json()
            print(f"  Keys: {list(data.keys())}")
            if 'list' in data:
                items = data['list']
                print(f"  {len(items)} filings")
                for item in items[:5]:
                    print(f"    {item.get('report_nm', '')} | {item.get('rcept_dt', '')} | {item.get('flr_nm', '')}")
    except Exception as e:
        print(f"  DART search ERROR: {e}")
    time.sleep(1)

    # Try DART viewer for financial data (HTML scraping of statements)
    # Annual report search for 한미반도체 2022
    url2 = "https://dart.fss.or.kr/dsab001/search.ax"
    params2 = {
        "textCrpCik": "",
        "textCrpNm": "한미반도체",
        "startDate": "20220101",
        "endDate": "20221231",
        "typeCode": "A001",  # 사업보고서
        "pageIndex": "1",
    }
    try:
        r2 = requests.get(url2, params=params2, headers=headers, timeout=15)
        print(f"\n  DART ax search status: {r2.status_code}, len={len(r2.text)}")
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(r2.text, 'html.parser')
        rows = soup.find_all('tr')
        print(f"  {len(rows)} tr tags")
        for row in rows[:10]:
            cells = [c.get_text(strip=True) for c in row.find_all(['td', 'th'])]
            if cells:
                print(f"    {cells[:5]}")
    except Exception as e:
        print(f"  DART ax search ERROR: {e}")


# ─────────────────────────────────────────────────────────────────
# 7. Yahoo Finance via yfinance
# ─────────────────────────────────────────────────────────────────
def test_yfinance():
    print("\n" + "="*60)
    print("7. yfinance (Yahoo Finance)")
    print("="*60)
    try:
        import yfinance as yf
    except ImportError:
        print("  yfinance not installed")
        return

    # Korean stocks on Yahoo Finance use .KS (KOSPI) or .KQ (KOSDAQ) suffix
    tickers_yf = [
        ("042700.KQ", "한미반도체"),  # KOSDAQ
        ("000660.KS", "SK하이닉스"),  # KOSPI
        ("298040.KS", "효성중공업"),  # KOSPI
    ]

    for yf_ticker, name in tickers_yf:
        print(f"\n--- {yf_ticker} ({name}) ---")
        try:
            tk = yf.Ticker(yf_ticker)

            # Annual income statement
            try:
                inc = tk.income_stmt
                print(f"  income_stmt: {inc.shape if inc is not None and not inc.empty else 'empty'}")
                if inc is not None and not inc.empty:
                    print(f"  Columns (years): {list(inc.columns)}")
                    key_rows = ['Total Revenue', 'Operating Income', 'Gross Profit']
                    for row_name in key_rows:
                        if row_name in inc.index:
                            print(f"    {row_name}: {dict(zip([str(c)[:10] for c in inc.columns], inc.loc[row_name].values))}")
            except Exception as e:
                print(f"  income_stmt ERROR: {e}")

            # Quarterly income statement
            try:
                inc_q = tk.quarterly_income_stmt
                print(f"  quarterly_income_stmt: {inc_q.shape if inc_q is not None and not inc_q.empty else 'empty'}")
                if inc_q is not None and not inc_q.empty:
                    print(f"  Columns (quarters): {[str(c)[:10] for c in inc_q.columns]}")
                    if 'Total Revenue' in inc_q.index:
                        print(f"  Revenue (quarterly): {dict(zip([str(c)[:10] for c in inc_q.columns], inc_q.loc['Total Revenue'].values))}")
                    if 'Operating Income' in inc_q.index:
                        print(f"  OpIncome (quarterly): {dict(zip([str(c)[:10] for c in inc_q.columns], inc_q.loc['Operating Income'].values))}")
            except Exception as e:
                print(f"  quarterly_income_stmt ERROR: {e}")

        except Exception as e:
            print(f"  ERROR: {e}")
        time.sleep(1)


# ─────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    tests = {
        "fdr": test_fdr,
        "fdr_detailed": test_fdr_detailed,
        "pykrx": test_pykrx,
        "naver": test_naver_finance,
        "naver_deep": test_naver_finance_deep,
        "krx_kind": test_krx_kind,
        "dart_public": test_dart_public,
        "yfinance": test_yfinance,
    }

    # Run all or specific tests
    if len(sys.argv) > 1:
        selected = sys.argv[1:]
        for name in selected:
            if name in tests:
                try:
                    tests[name]()
                except Exception as e:
                    print(f"\nFATAL in {name}: {e}")
                    traceback.print_exc()
    else:
        for name, fn in tests.items():
            try:
                fn()
            except Exception as e:
                print(f"\nFATAL in {name}: {e}")
                traceback.print_exc()

    print("\n" + "="*60)
    print("DONE")
    print("="*60)
