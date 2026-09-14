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

if not supabase_url or not supabase_key:
    print("Error: SUPABASE_URL or SUPABASE_SERVICE_KEY is missing from environment.")
    sys.exit(1)

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
    },
    {
        "theme": "조선/해운/에너지",
        "title": "중동 지정학적 위기 고조 및 물류 교란에 따른 친환경 선박(LNG/암모니아) 공급자 우위 극대화 가설",
        "date": today_str,
        "play_mode": "Global_Re_rating_Play",
        "background": (
            "[뉴스] 이란, UAE 바라카 원전 잠재 타겟 지목 / 한국, UAE 원유 긴급 비축 / 현대차 실적 쇼크. "
            "중동 확전 우려가 대형 에너지 인프라를 직접 위협하며 원유 수급 및 해상 물류망 교란을 초래. "
            "에너지 안보 강화를 위한 LNG 및 차세대 무탄소 선박 발주가 구조적으로 가속화."
        ),
        "causal_chain": (
            "지정학 리스크 및 에너지 안보 위협 → 기존 항로 교란 및 친환경 에너지(LNG 등) 장거리 해상 운송 수요 급증 (Q 증가) "
            "→ 조선소 도크 부족 심화에 따른 신조선가 지속 상승 (P 상승) "
            "→ 고부가가치 선박 위주 수주로 국내 대형 조선사 구조적 흑자폭 확대."
        ),
        "total_score": 88,
        "directness": 22,
        "leverage": 23,
        "scalability_or_rotation": 21,
        "technical_alignment": 22,
        "directness_reason": "전쟁 리스크와 선박/물류 부족 사태는 운임 급등 및 신조선가 상승이라는 재무적 숫자로 가장 빠르고 직접적으로 찍힘.",
        "leverage_reason": "선가 상승분은 원가 인상분을 제외하고 고스란히 영업이익으로 떨어지는 극단적인 레버리지 구조를 가짐.",
        "scalability_or_rotation_reason": "에너지 안보에서 시작해 탈탄소(Net-Zero) 친환경 선박 교체 사이클로 자연스럽게 장기 확장됨.",
        "technical_alignment_reason": "주요 조선주들이 10년 만의 슈퍼사이클에 진입하며 강력한 52주 신고가 근접 및 정배열 형성 중.",
        "market_timing": "실제 자동차 등 제조업 실적 쇼크가 발생하는 반면, 조선업은 수주 호조를 증명하며 실적 기반의 자금 피난처로 돋보임.",
        "critical_risk": "글로벌 경기 둔화로 인한 원유/가스 등 기초 물동량 급감, 후판 가격 등 원자재 가격 재급등 위험.",
        "raw_json": {},
        "candidates": [
            {"ticker": "009540", "name": "HD한국조선해양", "role": "조선중간지주/친환경선박", "near_52w_high": 92.0, "ret_1m": 12.0, "ret_3m": 35.0, "early_signal_score": 88.0, "signal_flag": "✅돌파직후"},
            {"ticker": "010140", "name": "삼성중공업", "role": "LNG선박/해양플랜트", "near_52w_high": 87.0, "ret_1m": 7.5, "ret_3m": 22.0, "early_signal_score": 77.0, "signal_flag": "🔺임박"}
        ],
        "created_at": now_str
    }
]

print(f"오늘 날짜({today_str}) 거시 가설 Supabase 업로드 중...")
for idea in ideas:
    theme = idea["theme"]
    delete_url = f"{supabase_url}/rest/v1/macro_ideas?date=eq.{today_str}&theme=eq.{urllib.parse.quote(theme)}"
    del_req = urllib.request.Request(delete_url, headers=headers, method='DELETE')
    try:
        with urllib.request.urlopen(del_req) as response:
            pass
    except Exception as e:
        pass

url = f"{supabase_url}/rest/v1/macro_ideas"
req = urllib.request.Request(url, data=json.dumps(ideas).encode('utf-8'), headers=headers, method='POST')

try:
    with urllib.request.urlopen(req) as response:
        if response.getcode() in [200, 201]:
            print("성공적으로 오늘 날짜의 데이터가 DB에 반영되었습니다.")
        else:
            print(f"Status code: {response.getcode()}")
except Exception as e:
    print("Error:", e)
    if hasattr(e, 'read'):
        print(e.read().decode('utf-8'))
