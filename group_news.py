import sys
import json
from collections import defaultdict

sys.stdout.reconfigure(encoding='utf-8')

with open("scratch_fetched_news.json", "r", encoding="utf-8") as f:
    data = json.load(f)

macro_news = data.get("macro_news", [])

# Let's group by major themes
categories = {
    "AI / Semiconductor / Power Grid": ["ai", "semiconductor", "chip", "power", "grid", "data center", "hbm", "nvidia", "amd", "intel", "tsmc", "samsung", "sk hynix", "전력", "변압기", "반도체"],
    "Energy / Shipping / Oil / Middle East": ["lng", "ammonia", "shipbuilder", "vessel", "tanker", "oil", "wti", "brent", "gas", "energy", "middle east", "iran", "israel", "유가", "조선", "정유", "해운"],
    "Defense / Geopolitics / Arms": ["defense", "arm", "military", "poland", "k2", "weapon", "방산", "군사", "우크라이나", "러시아", "신무기"],
    "Trade / Tariffs / Policy / FX / Rates": ["tariff", "trade", "fed", "rate", "inflation", "cpi", "pce", "fomc", "301", "232", "관세", "금리", "환율", "달러", "클래리티"],
    "Automotive / EV / Battery": ["battery", "ev", "auto", "car", "hyundai", "kia", "배터리", "2차전지", "전기차", "현대차", "기아"],
    "Nuclear / SMR / Infrastructure": ["nuclear", "smr", "uranium", "원전", "체코", "전력망"],
    "Bio / Healthcare": ["bio", "pharma", "fda", "glp-1", "obesity", "바이오", "제약", "임상"]
}

clusters = defaultdict(list)
unmatched = []

for m in macro_news:
    title = m.get("title") or ""
    summary = m.get("summary") or ""
    text = (title + " " + summary).lower()
    
    matched = False
    for cat_name, kw_list in categories.items():
        if any(kw in text for kw in kw_list):
            clusters[cat_name].append(m)
            matched = True
    if not matched:
        unmatched.append(m)

print("=== CLUSTER SUMMARY ===")
for cat_name, items in clusters.items():
    print(f"[{cat_name}]: {len(items)} items")
print(f"[Unmatched / Others]: {len(unmatched)} items")

with open("grouped_clusters.txt", "w", encoding="utf-8") as f:
    for cat_name, items in clusters.items():
        f.write(f"\n=========================================\n")
        f.write(f"CATEGORY: {cat_name} ({len(items)} items)\n")
        f.write(f"=========================================\n")
        # Deduplicate titles
        seen = set()
        for idx, item in enumerate(items, 1):
            t = item.get("title")
            if t in seen:
                continue
            seen.add(t)
            f.write(f"[{item.get('published_at')}] [{item.get('source')}] {t}\n")
            if item.get("summary"):
                f.write(f"   Summary: {item.get('summary')}\n")

    f.write(f"\n=========================================\n")
    f.write(f"CATEGORY: Unmatched / Others ({len(unmatched)} items)\n")
    f.write(f"=========================================\n")
    seen = set()
    for idx, item in enumerate(unmatched, 1):
        t = item.get("title")
        if t in seen:
            continue
        seen.add(t)
        f.write(f"[{item.get('published_at')}] [{item.get('source')}] {t}\n")

print("Saved grouped_clusters.txt")
