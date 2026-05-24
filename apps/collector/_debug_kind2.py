"""Debug KIND API - POST method."""
import urllib.request, urllib.parse, json, sys
if sys.stdout.encoding != 'utf-8':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from datetime import date, timedelta

today_str = date.today().strftime("%Y%m%d")
start_str = (date.today() - timedelta(days=7)).strftime("%Y%m%d")

# Try POST
url = "https://kind.krx.co.kr/disclosure/todaydisclosure.do"
form_data = urllib.parse.urlencode({
    "method": "searchTodayDisclosureSub",
    "pageIndex": "1",
    "perPage": "20",
    "marketType": "00",
    "searchCodeType": "",
    "corpName": "",
    "reportNm": "",
    "startDate": start_str,
    "endDate": today_str,
    "repIsuSrtCd": "",
    "orderMode": "0",
    "orderStat": "D",
}).encode('utf-8')

req = urllib.request.Request(
    url,
    data=form_data,
    headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json, text/html, */*",
        "Content-Type": "application/x-www-form-urlencoded",
        "Referer": "https://kind.krx.co.kr/disclosure/todaydisclosure.do",
        "X-Requested-With": "XMLHttpRequest",
    },
    method="POST"
)

try:
    with urllib.request.urlopen(req, timeout=15) as resp:
        status = resp.status
        raw = resp.read()
        # Try multiple encodings
        for enc in ['utf-8', 'euc-kr', 'cp949']:
            try:
                text = raw.decode(enc)
                break
            except:
                continue
        else:
            text = raw.decode('utf-8', errors='replace')

        print(f"HTTP Status: {status}")
        print(f"Content length: {len(raw)} bytes")
        print(f"First 1000 chars:\n{text[:1000]}")

        if text.strip().startswith('{') or text.strip().startswith('['):
            data = json.loads(text)
            print(f"\nJSON keys: {list(data.keys()) if isinstance(data, dict) else 'list'}")
            items = data.get('list') or data.get('data') or (data if isinstance(data, list) else [])
            print(f"Items count: {len(items)}")
            if items:
                print(f"\nFirst 3 items:")
                for i in items[:3]:
                    print(f"  {i}")

except Exception as e:
    print(f"POST failed: {e}")
    import traceback; traceback.print_exc()

# Try KRX OpenAPI (alternative)
print("\n--- KRX OpenAPI DART alternative: DART list ---")
# DART Open API (without key) has a limited endpoint
# Let's try the DART RSS feed which is public
dart_rss = "https://opendart.fss.or.kr/api/list.xml?page_no=1&page_count=20&sort=date&sort_mth=desc"
req2 = urllib.request.Request(dart_rss, headers={"User-Agent": "Mozilla/5.0"})
try:
    with urllib.request.urlopen(req2, timeout=10) as resp:
        text = resp.read().decode('utf-8', errors='replace')
        print(f"DART XML status: {resp.status}, length: {len(text)}")
        print(f"First 500: {text[:500]}")
except Exception as e:
    print(f"DART XML failed: {e}")
