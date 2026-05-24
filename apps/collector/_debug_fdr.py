"""Test FinanceDataReader for disclosure data."""
import sys
if sys.stdout.encoding != 'utf-8':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import FinanceDataReader as fdr
import inspect

# Check what FDR can do
print("FDR available functions:")
for name in dir(fdr):
    if not name.startswith('_'):
        print(f"  {name}")

print("\n--- Try FDR.DataReader for DART-like ---")
# FDR has DataReader function; try some known data sources
try:
    # KRX DART disclosure
    df = fdr.DataReader('DART', '2026-05-16', '2026-05-23')
    print(f"DART rows: {len(df)}, cols: {list(df.columns)}")
    if len(df) > 0:
        print(df.head(3))
except Exception as e:
    print(f"FDR DART failed: {e}")

# Try the krx module directly
try:
    from FinanceDataReader._utils import _KRX
    print("\nKRX module found")
except Exception as e:
    print(f"No _KRX: {e}")

# KRX OTC/market data - check if there's a disclosure endpoint
print("\n--- Check pykrx ---")
try:
    import pykrx
    print(f"pykrx available: {dir(pykrx)}")
except ImportError:
    print("pykrx not installed")

# Check httpx for direct KRX disclosure API
print("\n--- Direct KRX API test ---")
import httpx
# KRX has a publicly accessible API for market announcements
url = "https://data.krx.co.kr/comm/bldAttendant/getJsonData.cmd"
params = {
    "bld": "dbms/MDC/STAT/standard/MDCSTAT23901",  # 당일 공시 현황
    "locale": "ko_KR",
    "mktId": "STK",
    "fromDate": "20260516",
    "toDate": "20260523",
    "pageSize": "20",
    "pagePath": "/contents/MDC/STAT/standard/MDCSTAT23901",
}
headers = {
    "User-Agent": "Mozilla/5.0",
    "Referer": "https://data.krx.co.kr/",
    "Accept": "application/json",
}
try:
    with httpx.Client(timeout=15) as client:
        resp = client.post(url, data=params, headers=headers)
        print(f"Status: {resp.status_code}")
        text = resp.text
        print(f"Length: {len(text)}, First 500: {text[:500]}")
        if text.startswith('{'):
            import json
            data = json.loads(text)
            print(f"Keys: {list(data.keys())}")
except Exception as e:
    print(f"KRX API error: {e}")
