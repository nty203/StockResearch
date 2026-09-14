import os
import sys
import json
import urllib.request
import urllib.parse
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding='utf-8')
load_dotenv("apps/collector/.env")

supabase_url = os.environ.get("SUPABASE_URL")
supabase_key = os.environ.get("SUPABASE_SERVICE_KEY")

headers = {
    "apikey": supabase_key,
    "Authorization": f"Bearer {supabase_key}",
    "Content-Type": "application/json",
    "Prefer": "return=representation"
}

kst = timezone(timedelta(hours=9))
today_str = datetime.now(kst).strftime("%Y-%m-%d")
now_str = datetime.now(timezone.utc).isoformat()

ideas = [
    {
        "theme": "로봇/피지컬AI",
        "title": "LG전자-엔비디아 로봇 동맹 및 AI 유니콘 집중 육성에 따른 지능형 로봇 밸류체인 수혜 가설",
        "date": today_str,
        "play_mode": "Global_Re_rating_Play",
        "background": (
            "[뉴스] LG전자, 풀스택 피지컬 AI 로봇 상용화 본격화 / SKT-하나금융, AI 유니콘 발굴 포럼 개최. "
            "단순 생성형 AI를 넘어 물리적 공간에서 동작하는 '피지컬 AI(로봇)'로 산업의 무게중심이 이동 중이며, "
            "국내 대기업(LG, SKT)의 자본과 글로벌 기술력(엔비디아)이 결합하며 로봇 상용화 일정이 대폭 앞당겨지고 있음."
        ),
        "causal_chain": (
            "대기업의 AI/로봇 파트너십 및 집중 투자 → 서비스/산업용 지능형 로봇 양산 개시 (Q 증가) "
            "→ 정밀 감속기, 관절 모듈 등 로봇 핵심 부품의 수요 급증 및 단가 방어 (P 방어/상승) "
            "→ 로봇 부품사 및 소프트웨어(비전 AI 등) 기업들의 구조적 흑자 전환 및 이익률 극대화."
        ),
        "total_score": 90,
        "directness": 24,
        "leverage": 23,
        "scalability_or_rotation": 23,
        "technical_alignment": 20,
        "directness_reason": "대기업의 직접적인 B2B/B2C 로봇 양산 및 금융 지원은 국내 부품 밸류체인 수주로 즉각 연결됨.",
        "leverage_reason": "감속기 및 관절 모듈은 초기 R&D 비용이 크나, 양산 돌입 시 고정비 레버리지 효과로 폭발적 이익 성장이 가능.",
        "scalability_or_rotation_reason": "소프트웨어(AI) 위주에서 하드웨어(로봇)로 시장의 관심과 자금이 순환매되는 초기 국면.",
        "technical_alignment_reason": "현대오토에버, 로보티즈 등 관련 수혜주들이 52주 고점 근방에서 하방을 다지며 턴어라운드 조짐을 보임.",
        "market_timing": "순수 소프트웨어 AI의 고평가 논란 속에서 실체를 가진 하드웨어(로봇)가 새로운 투자 대안으로 떠오르는 최적의 타이밍.",
        "critical_risk": "글로벌 금리 인하 지연 시 기업들의 설비 투자(CAPEX) 및 로봇 도입 이연 가능성.",
        "raw_json": {},
        "candidates": [
            {"ticker": "307950", "name": "현대오토에버", "role": "자율주행/로봇SW플랫폼", "near_52w_high": 89.2, "ret_1m": 18.7, "ret_3m": -2.4, "early_signal_score": 65.0, "signal_flag": "🔺임박"},
            {"ticker": "108490", "name": "로보티즈", "role": "실외자율주행/LG지분", "near_52w_high": 80.7, "ret_1m": 10.3, "ret_3m": 9.9, "early_signal_score": 40.3, "signal_flag": "📌중기후보"}
        ],
        "created_at": now_str
    },
    {
        "theme": "전자부품/AI기판",
        "title": "첨단기술 육성 정책 및 반도체 업황 회복 기대감에 따른 AI 후공정/기판 업체 턴어라운드 가설",
        "date": today_str,
        "play_mode": "Domestic_Alternative_Play",
        "background": (
            "[뉴스] KIST 30주년 첨단기술 육성 / 반도체, AI 효과로 회복세 뚜렷 및 반도체 훈풍 기대감. "
            "정부 차원의 첨단 R&D(KIST 등) 지원 확대와 글로벌 AI 수요 폭증으로 국내 반도체 패키징 및 유리기판 등 차세대 전자부품 생태계의 낙수효과가 가시화됨."
        ),
        "causal_chain": (
            "글로벌 AI 반도체 수요 및 정부 지원책 가동 → 국내 AI 기판(FC-BGA, 유리기판) 및 후공정 장비 수주 확대 (Q 증가) "
            "→ 차세대 첨단 패키징 스펙 요구에 따른 공급 단가(ASP) 프리미엄 유지 (P 상승) "
            "→ 기판 및 후공정 소부장 업체들의 가동률 상승 및 영업이익률 V자 반등."
        ),
        "total_score": 86,
        "directness": 22,
        "leverage": 23,
        "scalability_or_rotation": 21,
        "technical_alignment": 20,
        "directness_reason": "AI 반도체 수요는 필수적으로 고다층 기판(FC-BGA) 및 어드밴스드 패키징 수요를 즉각적으로 견인함.",
        "leverage_reason": "기판 및 후공정은 대규모 장비 투자가 선행되는 산업으로, 가동률 회복 시 영업 레버리지가 매우 높음.",
        "scalability_or_rotation_reason": "HBM 이후 차세대 모멘텀인 유리기판(Glass Core) 등 신기술 패러다임 변화로 모멘텀 연장 가능성 큼.",
        "technical_alignment_reason": "삼성전기, 이수페타시스 등 주요 기판 업체들의 실적 바닥 통과 및 기관 수급 점진적 유입.",
        "market_timing": "HBM 관련주들의 급등에 따른 밸류에이션 부담을 피하면서도 AI 성장을 향유할 수 있는 훌륭한 대안처.",
        "critical_risk": "글로벌 IT 세트(스마트폰/PC) 수요 회복 지연 시 레거시 기판 부문의 적자 지속 리스크.",
        "raw_json": {},
        "candidates": [
            {"ticker": "009150", "name": "삼성전기", "role": "FC-BGA/유리기판대장", "near_52w_high": 75.0, "ret_1m": 4.5, "ret_3m": -5.0, "early_signal_score": 50.0, "signal_flag": "📌중기후보"},
            {"ticker": "007810", "name": "코리아써키트", "role": "반도체기판수혜주", "near_52w_high": 60.0, "ret_1m": 8.0, "ret_3m": 2.0, "early_signal_score": 45.0, "signal_flag": "📌중기후보"}
        ],
        "created_at": now_str
    }
]

print(f"새로운 뉴스 기반 오늘 날짜({today_str}) 거시 가설 Supabase 업로드 중...")
url = f"{supabase_url}/rest/v1/macro_ideas"
req = urllib.request.Request(url, data=json.dumps(ideas).encode('utf-8'), headers=headers, method='POST')

try:
    with urllib.request.urlopen(req) as response:
        if response.getcode() in [200, 201]:
            print("성공적으로 새로운 데이터가 DB에 반영되었습니다.")
        else:
            print(f"Status code: {response.getcode()}")
except Exception as e:
    print("Error:", e)
    if hasattr(e, 'read'):
        print(e.read().decode('utf-8'))
