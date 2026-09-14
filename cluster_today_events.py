import json
import re
from collections import defaultdict

with open("scratch_fetched_news.json", "r", encoding="utf-8") as f:
    data = json.load(f)

macro_news = data["macro_news"]
company_news = data["news"]

all_items = []
for item in macro_news:
    item['source_type'] = 'macro'
    all_items.append(item)
for item in company_news:
    item['source_type'] = 'company'
    all_items.append(item)

keywords_map = {
    "AI / 반도체 / HBM / BigTech CAPEX": [
        "반도체", "HBM", "AI", "빅테크", "CAPEX", "아마존", "AWS", "엔비디아", "SK하이닉스", "삼성전자",
        "한미반도체", "파운드리", "클라우드", "메모리", "패키징", "TSMC", "마이크론", "Intel", "인텔",
        "애플", "마이크로소프트", "MS", "구글", "알파벳", "메타"
    ],
    "전력기기 / 배전망 / 전력망 / SMP / LNG / 에너지가격": [
        "전력", "변압기", "배전", "송전", "전력망", "SMP", "한전", "LS ELECTRIC", "LS일렉트릭",
        "HD현대일렉트릭", "효성중공업", "원전", "원자력", "LNG", "천연가스", "유가", "WTI", "OPEC",
        "에너지", "Grid", "발전", "신재생", "태양광", "풍력"
    ],
    "방산 / 조선 / 함정 MRO / 지정학적 안보": [
        "방산", "조선", "한화에어로", "HD한국조선해양", "한화오션", "KDDX", "K9", "천무", "도크",
        "수주", "MRO", "미 해군", "MASGA", "우크라이나", "중동", "이스라엘", "이란", "안보", "군사",
        "방위산", "현대로템", "LIG넥스원", "K2", "전투기", "함정"
    ],
    "관세 / 미중 갈등 / 무역 / 공급망 규제 / 서플라이체인": [
        "관세", "트럼프", "바이든", "미중", "중국", "제재", "수출통제", "무역", "통상", "보호무역",
        "보조금", "IRA", "CHIPS", "칩스법"
    ],
    "금리 / 연준(Fed) / 환율 / 매크로 유동성 / CPI / 고용": [
        "금리", "연준", "Fed", "파월", "FOMC", "인플레이션", "CPI", "PPI", "고용", "실업",
        "환율", "달러", "국채", "수익률", "금리인하", "금리동결"
    ],
    "자동차 / 2차전지 / EV": [
        "현대차", "기아", "자동차", "2차전지", "배터리", "LG에너지솔루션", "삼성SDI", "에코프로",
        "포스코홀딩스", "양극재", "음극재", "전기차", "EV"
    ],
    "바이오 / 제약 / 의료": [
        "바이오", "제약", "임상", "FDA", "신약", "삼성바이오로직스", "셀트리온", "알테오젠", "HLB"
    ]
}

clusters = defaultdict(list)
unclustered = []

for item in all_items:
    title = item.get("title", "")
    summary = item.get("summary", "") or ""
    text = f"{title} {summary}"
    
    matched = False
    for theme, kw_list in keywords_map.items():
        if any(re.search(r'\b' + re.escape(kw) + r'\b', text, re.IGNORECASE) or kw in text for kw in kw_list):
            clusters[theme].append(item)
            matched = True
            
    if not matched:
        unclustered.append(item)

with open("scratch_clustered_summary.txt", "w", encoding="utf-8") as f:
    f.write(f"TOTAL ANALYZED ITEMS: {len(all_items)}\n\n")
    for theme, items in clusters.items():
        f.write(f"==================================================\n")
        f.write(f"THEME: {theme} ({len(items)} items)\n")
        f.write(f"==================================================\n")
        # Deduplicate titles
        seen = set()
        for item in items:
            t = item.get("title", "").strip()
            if t not in seen:
                seen.add(t)
                pub = item.get("published_at", "")[:16]
                src = item.get("source", "") or item.get("category", "")
                f.write(f"[{pub}] [{src}] {t}\n")
                summ = item.get("summary", "")
                if summ and len(summ) > 10:
                    f.write(f"  -> {summ[:150]}...\n")
        f.write("\n")

    f.write(f"==================================================\n")
    f.write(f"OTHER / UNCLUSTERED ({len(unclustered)} items)\n")
    f.write(f"==================================================\n")
    seen = set()
    for item in unclustered[:100]: # top 100
        t = item.get("title", "").strip()
        if t not in seen:
            seen.add(t)
            pub = item.get("published_at", "")[:16]
            f.write(f"[{pub}] {t}\n")

print("Cluster analysis completed. Output saved to scratch_clustered_summary.txt")
