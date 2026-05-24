"""Test NAVER Finance disclosure API."""
import sys
if sys.stdout.encoding != 'utf-8':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import httpx, json

# NAVER Finance: stock-specific news (includes disclosures mixed with news)
# URL pattern: https://finance.naver.com/item/news_invest.nhn?code=TICKER

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Referer": "https://finance.naver.com/",
    "Accept-Language": "ko-KR,ko;q=0.9",
}

# Test NAVER Finance company news API
# This API returns company news/disclosures as JSON
test_url = "https://finance.naver.com/item/new_invest.nhn"
params = {
    "code": "082740",  # HSD엔진
    "page": 1,
    "sm": "title_entity_id.basic",
}

print("=== NAVER Finance News/Disclosure Test ===")
with httpx.Client(timeout=15, follow_redirects=True) as client:
    resp = client.get(test_url, params=params, headers=HEADERS)
    print(f"Status: {resp.status_code}")
    print(f"Content-Type: {resp.headers.get('content-type', '?')}")
    print(f"Length: {len(resp.content)}")
    print(f"First 500:\n{resp.text[:500]}")

# Try the NAVER stock news API
print("\n=== NAVER Stock Sise/Disclosure (JSON) ===")
url2 = "https://m.stock.naver.com/api/stock/082740/news"
with httpx.Client(timeout=15, follow_redirects=True) as client:
    resp = client.get(url2, headers=HEADERS)
    print(f"Status: {resp.status_code}")
    print(f"Length: {len(resp.content)}")
    try:
        data = resp.json()
        print(f"Keys: {list(data.keys()) if isinstance(data, dict) else 'list len=' + str(len(data))}")
        if isinstance(data, list) and data:
            print(f"First item: {data[0]}")
        elif isinstance(data, dict):
            for k, v in list(data.items())[:3]:
                print(f"  {k}: {str(v)[:100]}")
    except:
        print(f"Non-JSON: {resp.text[:300]}")

# NAVER Finance 공시 전용 API
print("\n=== NAVER Finance Disclosure (공시) API ===")
url3 = "https://m.stock.naver.com/api/stock/082740/disclosure"
with httpx.Client(timeout=15, follow_redirects=True) as client:
    resp = client.get(url3, headers=HEADERS)
    print(f"Status: {resp.status_code}")
    print(f"Length: {len(resp.content)}")
    try:
        data = resp.json()
        print(f"Keys: {list(data.keys()) if isinstance(data, dict) else 'list'}")
        if isinstance(data, list) and data:
            print(f"Items: {len(data)}")
            for item in data[:3]:
                print(f"  {item}")
        elif isinstance(data, dict):
            for k, v in list(data.items())[:5]:
                print(f"  {k}: {str(v)[:150]}")
    except:
        print(f"Non-JSON: {resp.text[:500]}")

# Try another variant - 전자공시 API
print("\n=== NAVER Corp Info API ===")
url4 = "https://m.stock.naver.com/api/index/KOSPI/notice"
with httpx.Client(timeout=15, follow_redirects=True) as client:
    resp = client.get(url4, headers=HEADERS)
    print(f"Status: {resp.status_code}")
    print(f"First 500: {resp.text[:500]}")
