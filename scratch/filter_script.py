import json
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')

with open('scratch/current_raw_news.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

macro_news = data.get('macro_news', [])
company_news = data.get('news', [])

noise_patterns = [
    r'Earnings Call Presentation', r'Securities Fraud Lawsuit', r'Shareholder Notice',
    r'Go player', r'KataGo', r'치킨집', r'병무청', r'국세청', r'Chungho Nais', r'UFC'
]

meaningful = []
for m in macro_news:
    title = m.get('title') or ''
    summary = m.get('summary') or ''
    full_text = f'{title} {summary}'
    if any(re.search(pat, full_text, re.IGNORECASE) for pat in noise_patterns):
        continue
    meaningful.append(m)

print(f'Total Macro News: {len(macro_news)}, Meaningful Macro News: {len(meaningful)}')

with open('scratch/filtered_today_macro.txt', 'w', encoding='utf-8') as f:
    for idx, item in enumerate(meaningful, 1):
        pub = item.get("published_at", "")
        cat = item.get("category", "")
        src = item.get("source", "")
        title = item.get("title", "")
        summary = item.get("summary", "")
        f.write(f'[{idx:03d}] [{pub}] [{cat}] [{src}]\n')
        f.write(f'TITLE: {title}\n')
        if summary:
            f.write(f'SUMMARY: {summary}\n')
        f.write('-'*80 + '\n')

print('Saved scratch/filtered_today_macro.txt')
