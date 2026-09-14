import json
import re
import sys
from collections import defaultdict

sys.stdout.reconfigure(encoding='utf-8')

with open('scratch/current_raw_news.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

macro_news = data.get('macro_news', [])

# Keywords for topic clustering
topics = {
    "AI / 반도체 / 데이터센터": [r"AI", r"인공지능", r"반도체", r"HBM", r"엔비디아", r"NVIDIA", r"삼성", r"SK하이닉스", r"파운드리", r"칩", r"칩스", r"브로드컴", r"Broadcom", r"오픈AI", r"OpenAI", r"AIDC", r"클라우드", r"서버", r"데이터센터", r"SoC"],
    "전력 / 변압기 / 원전 / 에너지": [r"전력", r"변압기", r"송배전", r"배전", r"원전", r"원자력", r"에너지", r"LS", r"현대일렉트릭", r"효성중공업", r"전력망", r"발전", r"가스", r"LNG", r"원유", r"석유", r"유가", r"바라카"],
    "지정학 / 방산 / 조선 / 해운": [r"중동", r"이란", r"이스라엘", r"공습", r"제재", r"방산", r"조선", r"해운", r"유조선", r"LNG선", r"운반선", r"사할린", r"우크라이나", r"러시아", r"EU", r"안보", r"군사"],
    "거시경제 / 금리 / 환율 / 한국은행": [r"금리", r"한은", r"한국은행", r"BOK", r"Fed", r"연준", r"환율", r"원화", r"달러", r"물가", r"인플레", r"GDP", r"국채", r"채권"],
    "국내 정책 / 정치 / 지배구조 / 기업옥죄기": [r"대통령", r"이재명", r"정부", r"국회", r"정책", r"법안", r"세제", r"상법", r"밸류업", r"규제"],
    "바이오 / 헬스케어": [r"바이오", r"제약", r"백신", r"임상", r"FDA", r"신약", r"치매", r"암"]
}

clustered = defaultdict(list)
unclustered = []

for m in macro_news:
    title = m.get("title", "")
    summary = m.get("summary", "")
    full_text = f"{title} {summary}"
    
    matched = False
    for topic, kw_list in topics.items():
        for kw in kw_list:
            if re.search(kw, full_text, re.IGNORECASE):
                clustered[topic].append(m)
                matched = True
                break
    if not matched:
        unclustered.append(m)

print("=== CLUSTER SUMMARY ===")
for topic, items in clustered.items():
    print(f"[{topic}]: {len(items)} items")

print(f"[기타/미분류]: {len(unclustered)} items\n")

with open("scratch/today_clusters.txt", "w", encoding="utf-8") as f:
    for topic, items in clustered.items():
        f.write(f"=========================================\n")
        f.write(f"TOPIC: {topic} ({len(items)} items)\n")
        f.write(f"=========================================\n")
        seen_titles = set()
        for idx, item in enumerate(items, 1):
            title = item.get("title", "").strip()
            if title in seen_titles:
                continue
            seen_titles.add(title)
            pub = item.get("published_at", "")[:19]
            summary = item.get("summary", "")
            f.write(f"{idx}. [{pub}] {title}\n")
            if summary:
                f.write(f"   Summary: {summary}\n")
        f.write("\n")

    f.write(f"=========================================\n")
    f.write(f"TOPIC: 기타/미분류 ({len(unclustered)} items)\n")
    f.write(f"=========================================\n")
    seen_titles = set()
    for idx, item in enumerate(unclustered, 1):
        title = item.get("title", "").strip()
        if title in seen_titles:
            continue
        seen_titles.add(title)
        pub = item.get("published_at", "")[:19]
        summary = item.get("summary", "")
        f.write(f"{idx}. [{pub}] {title}\n")
        if summary:
            f.write(f"   Summary: {summary}\n")

print("Saved to scratch/today_clusters.txt")
