"""Debug KIND API response."""
import urllib.request, json, sys
if sys.stdout.encoding != 'utf-8':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from datetime import date, timedelta

today_str = date.today().strftime("%Y%m%d")
start_str = (date.today() - timedelta(days=7)).strftime("%Y%m%d")

print(f"Today: {today_str}, Start: {start_str}")

# Try the API
url = (
    "https://kind.krx.co.kr/disclosure/todaydisclosure.do"
    f"?method=searchTodayDisclosureSub&pageIndex=1&perPage=20"
    f"&marketType=00&searchCodeType=&corpName=&reportNm=&startDate={start_str}&endDate={today_str}"
    "&repIsuSrtCd=&orderMode=0&orderStat=D"
)
print(f"URL: {url}")

req = urllib.request.Request(
    url,
    headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json, text/javascript, */*",
        "Referer": "https://kind.krx.co.kr/disclosure/todaydisclosure.do",
    }
)

try:
    with urllib.request.urlopen(req, timeout=15) as resp:
        status = resp.status
        raw = resp.read()
        text = raw.decode('utf-8', errors='replace')
        print(f"HTTP Status: {status}")
        print(f"Content length: {len(raw)} bytes")
        print(f"First 500 chars:\n{text[:500]}")

        # Try to parse as JSON
        try:
            data = json.loads(text)
            print(f"\nJSON keys: {list(data.keys())}")
            items = data.get('list') or data.get('data') or []
            print(f"Items count: {len(items)}")
            if items:
                print(f"First item: {items[0]}")
        except json.JSONDecodeError as e:
            print(f"JSON parse error: {e}")
            print("Response is HTML or non-JSON")

except Exception as e:
    print(f"Request failed: {e}")

# Try alternate URL format
print("\n--- Trying alternate URL ---")
url2 = "https://kind.krx.co.kr/disclosure/todaydisclosure.do?method=searchTodayDisclosureMain"
req2 = urllib.request.Request(url2, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"})
try:
    with urllib.request.urlopen(req2, timeout=15) as resp:
        text = resp.read().decode('utf-8', errors='replace')
        print(f"Status: {resp.status}, Length: {len(text)}")
        print(f"First 300 chars: {text[:300]}")
except Exception as e:
    print(f"Alt URL failed: {e}")
