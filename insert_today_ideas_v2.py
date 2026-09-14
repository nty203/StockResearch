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
        "title": "LG전자-엔비디아 로봇 연합 및 SKT-하나금융 AI 투자 본격화에 따른 지능형 로봇 밸류체인 수혜 가설",
        "date": today_str,
        "play_mode": "Global_Re_rating_Play",
        "background": (
            "[최신 수집 뉴스] LG전자, 풀스택 피지컬 AI 로봇 상용화 본격화 / SKT-하나금융, AI 유니콘 발굴 포럼 개최. "
            "단순 생성형 AI를 넘어 물리적 공간에서 동작하는 '피지컬 AI(로봇)'로 산업의 무게중심이 이동 중. "
            "대기업(LG, SKT)의 자본과 글로벌 기술력(엔비디아)이 결합하며 로봇 상용화 일정이 앞당겨짐."
        ),
        "causal_chain": (
            "대기업의 AI/로봇 파트너십 및 자본 투입 → 서비스/산업용 지능형 로봇 양산 개시 (Q 증가) "
            "→ 정밀 감속기, 관절 모듈, 비전 센서 등 핵심 부품의 선도적 단가 협상력 유지 (P 상승) "
            "→ 로봇 부품사 및 소프트웨어 플랫폼 기업의 구조적 흑자 전환 및 이익률 급증."
        ),
        "total_score": 89,
        "directness": 24,
        "leverage": 22,
        "scalability_or_rotation": 23,
        "technical_alignment": 20,
        "directness_reason": "대기업의 직접적인 B2B/B2C 로봇 양산 및 금융 지원은 부품사 수주로 즉각 연결됨.",
        "leverage_reason": "감속기 및 관절 모듈은 초기 R&D 비용이 크나, 양산 돌입 시 고정비 효과로 폭발적 이익 성장이 가능.",
        "scalability_or_rotation_reason": "소프트웨어(AI) 위주에서 하드웨어(로봇)로 시장의 관심이 순환매되는 초입 국면.",
        "technical_alignment_reason": "현대오토에버, 로보티즈 등 관련 수혜주들이 하락 추세를 벗어나 턴어라운드 조짐을 보임.",
        "market_timing": "순수 소프트웨어 AI의 고평가 논란 속에서, 실체를 가진 하드웨어(로봇)가 새로운 대안으로 떠오르는 최적의 타이밍.",
        "critical_risk": "글로벌 금리 인하 지연 시, 기업들의 설비 투자(CAPEX) 및 로봇 도입 지연 가능성.",
        "raw_json": {},
        "candidates": [
            {"ticker": "307950", "name": "현대오토에버", "role": "자율주행/SW플랫폼", "near_52w_high": 89.2, "ret_1m": 18.7, "ret_3m": -2.4, "early_signal_score": 65.0, "signal_flag": "🔺임박"},
            {"ticker": "108490", "name": "로보티즈", "role": "실외자율주행로봇/LG지분", "near_52w_high": 80.7, "ret_1m": 10.3, "ret_3m": 9.9, "early_signal_score": 40.3, "signal_flag": "📌중기후보"}
        ],
        "created_at": now_str
    },
    {
        "theme": "원전/전력 인프라",
        "title": "AI 전력 보틀넥 심화 및 SMR 상용화 본격화에 따른 원전 주기기/전력기기 슈퍼사이클 가설",
        "date": today_str,
        "play_mode": "Global_Re_rating_Play",
        "background": (
            "[뉴스] 테라파워 상업용 SMR 건설 미국 승인 / AI 전력 트레이드 부각. "
            "빌 게이츠의 테라파워가 최초의 상업용 SMR 건설 승인을 획득하여 SMR 상용화가 당장의 현실로 다가왔으며, "
            "빅테크의 AI 데이터센터 확장으로 인한 전력(기저부하) 부족 현상이 원전 르네상스를 강력히 추동 중."
        ),
        "causal_chain": (
            "AI 전력 수요 폭증 및 SMR 건설 승인 → 대형 전력망 및 SMR 신규 수주 사이클 진입 (Q 증가) "
            "→ 리드 타임이 긴 원전 주기기 및 변압기 공급 부족 (P 상승) "
            "→ 밸류체인 판가 상승 및 설계/제조사들의 이익률 급증."
        ),
        "total_score": 92,
        "directness": 25,
        "leverage": 23,
        "scalability_or_rotation": 24,
        "technical_alignment": 20,
        "directness_reason": "미국 내 상업용 SMR 최초 승인은 국내 기자재/설계 업체들의 수주로 직접 연결될 가시성이 매우 높음.",
        "leverage_reason": "원전 주기기 및 초고압 변압기는 고정비가 크고 도크/캐파가 한정되어 있어 수요 초과시 이익 레버리지가 극대화됨.",
        "scalability_or_rotation_reason": "순수 테크(AI 반도체)에서 전력 인프라(AI Power)로 글로벌 자금이 로테이션되는 핵심 길목에 위치.",
        "technical_alignment_reason": "주요 전력기기/원전주들의 중장기 우상향 추세 견고 및 최근 변동성 장세에서도 강력한 하방 경직성 확보.",
        "market_timing": "테크/반도체 주도주의 변동성이 커지는 가운데, 방어적이면서도 AI 성장성을 향유할 수 있는 완벽한 피난처 및 주도주.",
        "critical_risk": "금리 인하 지연에 따른 프로젝트 파이낸싱(PF) 이자 부담 및 정책 규제에 의한 건설 스케줄 지연 가능성.",
        "raw_json": {},
        "candidates": [
            {"ticker": "034020", "name": "두산에너빌리티", "role": "원전주기기/SMR대장", "near_52w_high": 85.0, "ret_1m": 5.0, "ret_3m": 12.0, "early_signal_score": 80.0, "signal_flag": "🔺임박"},
            {"ticker": "267260", "name": "HD현대일렉트릭", "role": "초고압변압기대장", "near_52w_high": 90.0, "ret_1m": 8.0, "ret_3m": 25.0, "early_signal_score": 85.0, "signal_flag": "✅돌파직후"},
            {"ticker": "010120", "name": "LS일렉트릭", "role": "배전반/전력기기", "near_52w_high": 88.0, "ret_1m": 6.5, "ret_3m": 18.0, "early_signal_score": 75.0, "signal_flag": "🔺임박"}
        ],
        "created_at": now_str
    }
]

print(f"최신 뉴스 기반 오늘 날짜({today_str}) 거시 가설 Supabase 업데이트 중...")

# Delete old ideas for today to ensure fresh ones are shown
delete_url = f"{supabase_url}/rest/v1/macro_ideas?date=eq.{today_str}"
del_req = urllib.request.Request(delete_url, headers=headers, method='DELETE')
try:
    with urllib.request.urlopen(del_req) as response:
        print("기존 오늘 날짜 가설 초기화 완료")
except Exception as e:
    print("기존 가설 삭제 중 오류:", e)

# Insert new ideas
url = f"{supabase_url}/rest/v1/macro_ideas"
req = urllib.request.Request(url, data=json.dumps(ideas).encode('utf-8'), headers=headers, method='POST')

try:
    with urllib.request.urlopen(req) as response:
        if response.getcode() in [200, 201]:
            print("최신 수집 뉴스 기반 매크로 테마가 DB에 완벽히 반영되었습니다.")
        else:
            print(f"Status code: {response.getcode()}")
except Exception as e:
    print("Error:", e)
