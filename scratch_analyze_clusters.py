import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

with open("scratch_fetched_news.json", "r", encoding="utf-8") as f:
    data = json.load(f)

macro_news = data.get("macro_news", [])

print(f"Total macro news: {len(macro_news)}")

# Let's inspect titles containing key macro event triggers
keywords_to_check = [
    "트럼프", "관세", "금리", "연준", "fomc", "cpi", "pce", "환율", "달러",
    "미국", "중국", "바이든", "해리스", "우크라이나", "러시아", "중동", "이란", "이스라엘",
    "엔비디아", "하이니스크", "삼성전자", "hbm", "전력", "변압기", "원전", "smr", "조선", "lng",
    "배터리", "2차전지", "방산", "한화오션", "hd현대", "ls", "현대차", "바이오", "fda", "수출"
]

grouped = {}
for m in macro_news:
    title = m.get("title", "")
    summary = m.get("summary", "")
    pub = m.get("published_at", "")
    src = m.get("source", "")
    cat = m.get("category", "")
    
    # check date
    grouped.setdefault(cat, []).append((pub, src, title, summary))

with open("scratch_cluster_details.txt", "w", encoding="utf-8") as out:
    for cat, items in grouped.items():
        out.write(f"====================================\n")
        out.write(f"CATEGORY: {cat} ({len(items)} items)\n")
        out.write(f"====================================\n")
        seen_t = set()
        for pub, src, title, summary in items:
            if title in seen_t:
                continue
            seen_t.add(title)
            out.write(f"[{pub}] [{src}] {title}\n")
            if summary:
                out.write(f"   Summary: {summary}\n")

print("Saved scratch_cluster_details.txt")
