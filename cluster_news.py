import sys
import json
from collections import Counter

sys.stdout.reconfigure(encoding='utf-8')

with open("scratch_fetched_news.json", "r", encoding="utf-8") as f:
    data = json.load(f)

macro_news = data.get("macro_news", [])
company_news = data.get("news", [])

# Let's inspect all macro news titles and categories cleanly
print(f"=== MACRO NEWS SAMPLES ({len(macro_news)}) ===")
for i, m in enumerate(macro_news[:50], 1):
    title = m.get("title") or ""
    cat = m.get("category") or ""
    pub = m.get("published_at") or ""
    src = m.get("source") or ""
    print(f"[{i:02d}] [{pub}] [{cat}] [{src}] {title}")

print("\n=== COMPANY NEWS SAMPLES ({len(company_news)}) ===")
for i, c in enumerate(company_news[:50], 1):
    title = c.get("title") or ""
    pub = c.get("published_at") or ""
    print(f"[{i:02d}] [{pub}] {title}")
