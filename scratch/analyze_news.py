import json

with open('scratch/today_news_fetch.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

macro_news = data.get('macro_news', [])
news = data.get('news', [])

with open('scratch/parsed_news.txt', 'w', encoding='utf-8') as out:
    out.write(f"=== MACRO NEWS ({len(macro_news)} items) ===\n")
    for i, m in enumerate(macro_news):
        out.write(f"[{i+1}] [{m.get('published_at')}] [{m.get('category')}] {m.get('title')}\n")
        if m.get('summary'):
            out.write(f"    Summary: {m.get('summary')}\n")

    out.write(f"\n=== COMPANY NEWS ({len(news)} items) ===\n")
    for i, c in enumerate(news):
        out.write(f"[{i+1}] [{c.get('published_at')}] [{c.get('ticker')}] {c.get('title')}\n")

print("Saved to scratch/parsed_news.txt")
