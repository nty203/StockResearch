import json
import re
import sys
from collections import Counter

sys.stdout.reconfigure(encoding='utf-8')

with open("scratch/clean_macro_headlines.txt", "r", encoding="utf-8") as f:
    text = f.read()

articles = text.split("-" * 80)

print(f"Total articles parsed: {len(articles)}")

# Search key topics
topics = [
    ("NVIDIA / AI / Semiconductor / HBM", r"NVIDIA|엔비디아|HBM|반도체|웨이퍼|파운드리|브로드컴|Broadcom|MS|마이크로소프트|xAI|메모리|삼성|SK하이닉스|Qualcomm|퀄컴"),
    ("Power / Energy Grid / AIDC / Nuclear", r"전력|변압기|송배전|원전|원자력|바라카|Candu|태양광|에너지|Power|Grid|LS|현대일렉트릭|효성중공업"),
    ("Middle East War / Geopolitics / Military / Defense / Oil / Shipping", r"중동|이란|이스라엘|공습|미군|F-35|전투기|호르무즈|유가|원유|유조선|조선|마스가|MASGA|방산|국제유가|셸|LNG|사할린"),
    ("Fed / BOE / BOK / Rates / Inflation / FX", r"Fed|연준|BOK|한은|한국은행|금리|환율|원화|엔화|시장개입|Warsh|워시|BOE|물가|국채"),
    ("US-Korea IRA / Policy / Regulation / Space / SpaceX", r"IRA|한국판 IRA|SpaceX|스페이스X|ETF|개인정보|과징금|제재|미국")
]

for name, pattern in topics:
    matches = [a for a in articles if re.search(pattern, a, re.IGNORECASE)]
    print(f"\n==========================================")
    print(f"THEME: {name} ({len(matches)} articles)")
    print(f"==========================================")
    for m in matches[:15]:
        lines = [l.strip() for l in m.strip().split("\n") if l.strip()]
        if lines:
            print("  " + " | ".join(lines[:2]))
