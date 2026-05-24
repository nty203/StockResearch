"""Debug public RSS feeds for Korean disclosures."""
import urllib.request, sys
if sys.stdout.encoding != 'utf-8':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import feedparser

feeds = [
    ("KIND RSS", "https://kind.krx.co.kr/rss/todaydisclosure.xml"),
    ("KIND RSS 2", "https://kind.krx.co.kr/rss/disclosure.do"),
    ("DART RSS", "https://opendart.fss.or.kr/rss/dart.do"),
    ("DART RSS2", "https://opendart.fss.or.kr/rss/todaydisclosure.do"),
]

for name, url in feeds:
    print(f"\n--- {name}: {url} ---")
    try:
        feed = feedparser.parse(url)
        print(f"Status: {feed.get('status', '?')}")
        print(f"Entries: {len(feed.entries)}")
        if feed.entries:
            for e in feed.entries[:3]:
                print(f"  Title: {e.get('title', '?')[:80]}")
                print(f"  Link:  {e.get('link', '?')[:80]}")
        else:
            # Check if there's a bozo error
            if feed.bozo:
                print(f"  Bozo error: {feed.bozo_exception}")
            # Print raw
            raw = str(feed)[:300]
            print(f"  Raw (300): {raw}")
    except Exception as e:
        print(f"  Error: {e}")

# Also try NAVER Finance disclosure API
print("\n--- NAVER Finance Disclosure ---")
import urllib.request, json
url = "https://finance.naver.com/news/news_list.naver?mode=LSS3D&section0=101&section1=261&section2=&date=&page=1"
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
try:
    with urllib.request.urlopen(req, timeout=10) as resp:
        text = resp.read().decode('euc-kr', errors='replace')
        print(f"Status: {resp.status}, Length: {len(text)}")
        print(f"First 500: {text[:500]}")
except Exception as e:
    print(f"NAVER error: {e}")
