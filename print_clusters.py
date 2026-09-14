import sys
import json
from collections import defaultdict

sys.stdout.reconfigure(encoding='utf-8')

with open("scratch_fetched_news.json", "r", encoding="utf-8") as f:
    data = json.load(f)

macro_news = data.get("macro_news", [])

# Let's inspect unique titles per category
categories = {
    "AI / Power / Data Center / Semi": ["ai", "semiconductor", "chip", "power", "grid", "data center", "hbm", "nvidia", "amd", "intel", "tsmc", "samsung", "sk hynix", "전력", "변압기", "반도체"],
    "Energy / Shipping / LNG / Oil / Middle East": ["lng", "ammonia", "shipbuilder", "vessel", "tanker", "oil", "wti", "brent", "gas", "energy", "middle east", "iran", "israel", "유가", "조선", "정유", "해운", "가스공사"],
    "Defense / Geopolitics": ["defense", "arm", "military", "poland", "k2", "weapon", "방산", "군사", "우크라이나", "러시아", "신무기", "클래리티"],
    "Trade / Tariff / Policy / Macro": ["tariff", "trade", "fed", "rate", "inflation", "cpi", "pce", "fomc", "301", "232", "관세", "금리", "환율", "달러"],
    "Battery / EV / Auto": ["battery", "ev", "auto", "car", "hyundai", "kia", "배터리", "2차전지", "전기차", "현대차", "기아", "흑연"],
    "Nuclear / SMR": ["nuclear", "smr", "uranium", "원전", "체코"]
}

for cat_name, kw_list in categories.items():
    print(f"\n=========================================")
    print(f"=== {cat_name} ===")
    print(f"=========================================")
    seen = set()
    count = 0
    for m in macro_news:
        title = m.get("title") or ""
        summary = m.get("summary") or ""
        text = (title + " " + summary).lower()
        if any(kw in text for kw in kw_list):
            if title not in seen:
                seen.add(title)
                count += 1
                print(f"[{count:02d}] [{m.get('published_at')}] [{m.get('source')}] {title}")
                if summary and len(summary) > 5:
                    print(f"     Summary: {summary[:150]}...")
