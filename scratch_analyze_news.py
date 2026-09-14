import json
import re
from collections import defaultdict

with open("scratch_fetched_news.json", "r", encoding="utf-8") as f:
    data = json.load(f)

macro_news = data.get("macro_news", [])
company_news = data.get("news", [])

print(f"Total Macro News: {len(macro_news)}")
print(f"Total Company News: {len(company_news)}")

# Print all macro titles with published_at to get full view
with open("macro_titles.txt", "w", encoding="utf-8") as f:
    f.write(f"=== MACRO NEWS TITLES ({len(macro_news)}) ===\n")
    for i, item in enumerate(macro_news, 1):
        f.write(f"{i:03d}. [{item.get('published_at')}] [{item.get('category')}] [{item.get('source')}] {item.get('title')}\n")
        if item.get('summary'):
            f.write(f"     Summary: {item.get('summary')}\n")

with open("company_titles.txt", "w", encoding="utf-8") as f:
    f.write(f"=== COMPANY NEWS TITLES ({len(company_news)}) ===\n")
    for i, item in enumerate(company_news, 1):
        f.write(f"{i:03d}. [{item.get('published_at')}] {item.get('title')}\n")
        if item.get('summary'):
            f.write(f"     Summary: {item.get('summary')}\n")

print("Wrote macro_titles.txt and company_titles.txt")
