import json
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')

with open('scratch/current_raw_news.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

macro_news = data.get('macro_news', [])

noise_kw = [
    "배우", "가수", "임영웅", "이지혜", "김혜수", "장윤정", "황정음", "비비", "오타니", "홍명보",
    "UFC", "라이더", "맛피아", "스윙스", "연예계", "이혼", "사망설", "홈런", "챔피언", "인테리어",
    "고우석", "시라카와", "이범호", "나솔사계", "워터밤", "청담", "초고가", "누수"
]

clean_news = []
for item in macro_news:
    title = item.get("title", "")
    summary = item.get("summary", "")
    full_text = f"{title} {summary}"
    if any(kw in full_text for kw in noise_kw):
        continue
    clean_news.append(item)

print(f"Clean Macro News Count: {len(clean_news)}")

with open("scratch/clean_macro_headlines.txt", "w", encoding="utf-8") as f:
    for idx, item in enumerate(clean_news, 1):
        pub = item.get("published_at", "")[:19]
        cat = item.get("category", "")
        src = item.get("source", "")
        title = item.get("title", "")
        summary = item.get("summary", "")
        f.write(f"[{idx:03d}] [{pub}] [{cat}] [{src}]\n")
        f.write(f"TITLE: {title}\n")
        if summary:
            f.write(f"SUMMARY: {summary}\n")
        f.write("-" * 80 + "\n")

print("Saved to scratch/clean_macro_headlines.txt")
