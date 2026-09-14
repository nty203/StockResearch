import os
import sys
import json
import urllib.request
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
        "theme": "트럼프의 美 군함 해외 건조 파격 허용 및 한·미 방산·조선 MRO 동맹 가속화 (한화오션·HD한국조선해양)",
        "title": "미국 내 도크 부족 해소를 위한 한국 본토 도크 활용 승인 및 조선사 고마진 MRO/함정 수주 랠리",
        "date": today_str,
        "play_mode": "Global_Re_rating_Play",
        "background": (
            "[속보] 트럼프 미국 대통령, 미국에 투자한 해외 조선사가 모국(한국) 도크에서 최대 2척의 미 해군 군함 및 지원함을 건조할 수 있도록 예외 승인 파격 발표.\n"
            "Proxy: 미 해군 함정 MRO 수주 파이프라인 및 신조선가 지수 상승세 지속"
        ),
        "causal_chain": (
            "미 국방/해군 함정 생산 한계 및 도크 병목 → 트럼프 해외 투자 조선사 모국 건조 허용 행정조치 → 한국 대형 조선사(한화오션, HD한국조선해양)의 본토 도크 직접 활용 수주 승인 → 고부가가치 함정 MRO 및 건조 마진 극대화 → 조선 섹터 전반의 실적 가시성 및 Valuation 재평가"
        ),
        "total_score": 95,
        "directness": 25,
        "leverage": 24,
        "scalability_or_rotation": 23,
        "technical_alignment": 23,
        "directness_reason": "미국 해군 함정 해외 건조 규제 완화는 한국 조선소 도크 가동률과 직접 연결",
        "leverage_reason": "고마진 방산/MRO 수주가 합쳐지며 신조선가 상승과 함께 단가 이익 레버리지 극대화",
        "scalability_or_rotation_reason": "단순 상선 수주를 넘어 미 해군 MRO 및 군함 수주라는 사상 최초의 거대 방산 시장 개척",
        "technical_alignment_reason": "최근 기관/외인 수급 유입 및 주가 눌림목 형성 완료로 강한 수시 시그널 형성",
        "market_timing": "0-6개월",
        "critical_risk": "미국 의회의 존스법(Jones Act) 개정 진통 및 미국 내 노조의 집단 반발로 인한 세부 지침 지연 가능성",
        "raw_json": {
            "evidence_score": 20,
            "surprise_level": "Large",
            "root_driver": "미 해군 함정 도크 병목 및 트럼프 행정부의 한국 도크 군함 건조 전격 예외 승인 (Policy / War & Physical Supply)",
            "prior_belief": "미 군함은 존스법 및 해군 규정에 따라 100% 미국 본토 조선소에서만 건조/정비되어 한국 도크 직접 활용은 불가능하다.",
            "posterior_belief": "미국 내 도크 부족을 타개하기 위해 미국 투자 한국 조선사에 한해 모국(한국) 도크에서 미 군함 건조/MRO를 허용하는 구조적 제도 변화가 시작된다.",
            "revision_size": 92,
            "variant_view": {
                "consensus": "트럼프의 조선 발언은 미국 내 투자만을 압박하는 정치적 멘트에 불과하다.",
                "my_view": "미 해군의 현저한 도크 부족(Bottleneck)으로 인해 한국 본토 도크 직접 활용 허용은 필연적이었으며, 이는 한국 조선사들의 사상 최대 고마진 모멘텀으로 작용한다."
            },
            "transmission_confidence": "High",
            "bottleneck_rank": ["Shipbuilding Capacity", "Naval Dock Availability"]
        },
        "candidates": [
            {"ticker": "042660", "name": "한화오션", "role": "필리 조선소 인수를 통한 미국 투자 요건 충족 및 미 해군 MRO/함정 직접 수혜", "near_52w_high": 95.0, "ret_1m": 12.0, "ret_3m": 28.0, "early_signal_score": 95.0, "signal_flag": "🔺임박"},
            {"ticker": "009540", "name": "HD한국조선해양", "role": "미 해군 MSRA 체결 및 글로벌 1위 특수선/친환경선 도크 가동률 극대화", "near_52w_high": 90.0, "ret_1m": 8.0, "ret_3m": 22.0, "early_signal_score": 92.0, "signal_flag": "🟢관심"}
        ],
        "created_at": now_str
    },
    {
        "theme": "AI 패러다임의 '피지컬 AI(Physical AI) & SMR 전력 인프라' 결합 가속화 (두산에너빌리티·LG전자)",
        "title": "엔비디아-LG 피지컬 AI 동맹 및 빌 게이츠 SMR 상업화 계약 체결에 따른 AI 실물/에너지 인프라 대전환",
        "date": today_str,
        "play_mode": "Global_Re_rating_Play",
        "background": (
            "[뉴스] 엔비디아-LG그룹 피지컬 AI·자율제조·데이터센터 3대 초대형 동맹 구체화. 빌 게이츠 방한 및 한수원·SK-테라파워 SMR 상업화 계약 체결.\n"
            "Proxy: AI 데이터센터 전력 장기 구매 계약(PPA) 및 휴머노이드/로봇 밸류체인 수주 확대"
        ),
        "causal_chain": (
            "AI 기술의 가상(소프트웨어)에서 실물(피지컬 AI/로봇)로의 확장 + AIDC 전력난 심화 → 빌 게이츠 테라파워 SMR 상업화 체결 & 엔비디아-LG 피지컬 AI 결합 → SMR 주기기 및 로봇/공장자동화 기자재 수주 폭증 → 턴어라운드 및 장기 실적 성장"
        ),
        "total_score": 93,
        "directness": 24,
        "leverage": 23,
        "scalability_or_rotation": 23,
        "technical_alignment": 23,
        "directness_reason": "빌 게이츠 SMR 상업화 계약 체결 및 피지컬 AI 동맹은 SMR 주기기 및 AI 가전/로봇 수주와 직결",
        "leverage_reason": "SMR 진입장벽에 따른 공급자 독점 지위 확보 및 쿨링/자동화 솔루션의 고마진 레버리지",
        "scalability_or_rotation_reason": "단순 AI 소프트웨어에서 에너지원(SMR)과 실물 로봇(Physical AI)으로 AI 파이프라인의 전면 확장",
        "technical_alignment_reason": "원전/SMR 및 로봇 관련 주도주 바닥권 수급 재유입 및 상승 돌파 시도",
        "market_timing": "3-6개월",
        "critical_risk": "SMR 인허가 규제 기관의 검토 지연 및 피지컬 AI 상용화 속도의 단기 미달 가능성",
        "raw_json": {
            "evidence_score": 20,
            "surprise_level": "Large",
            "root_driver": "AI 인프라의 피지컬 AI(실물 로봇/공장) 진화 및 SMR(소형원전) 전력망 결합 (Physical Supply / CAPEX & Technology Shift)",
            "prior_belief": "AI 모멘텀은 엔비디아 GPU 수급과 소프트웨어 수익화에만 한정되며 SMR 원전 상업화는 먼 미래 일이다.",
            "posterior_belief": "AI 산업이 피지컬 AI와 SMR 청정 전력 결합으로 진화함에 따라 SMR 주기기 제조업체와 피지컬 AI 솔루션 기업이 차세대 주도 섹터로 부상한다.",
            "revision_size": 88,
            "variant_view": {
                "consensus": "AI 서버 우려로 관련 인프라주들의 주가 상승세가 둔화될 것이다.",
                "my_view": "피지컬 AI와 SMR 전력의 실제 상업화 계약이 체결되면서 AI 투자의 패러다임이 실물 전력 및 로봇 장비로 전면 전환된다."
            },
            "transmission_confidence": "High",
            "bottleneck_rank": ["SMR Power Infrastructure", "Physical AI System Integration"]
        },
        "candidates": [
            {"ticker": "034020", "name": "두산에너빌리티", "role": "빌 게이츠 테라파워 SMR 핵심 주기기 독점 제작 및 원전 르네상스 최대 수혜", "near_52w_high": 94.0, "ret_1m": 15.0, "ret_3m": 35.0, "early_signal_score": 94.0, "signal_flag": "🔺임박"},
            {"ticker": "066570", "name": "LG전자", "role": "엔비디아 피지컬 AI·AI 팩토리 동맹 및 데이터센터 칠러(액체냉각) 공급", "near_52w_high": 88.0, "ret_1m": 4.0, "ret_3m": 16.0, "early_signal_score": 91.0, "signal_flag": "🟢관심"}
        ],
        "created_at": now_str
    },
    {
        "theme": "미국 드론 100% 징벌적 관세 부과 및 韓 방산/감시 체계 반사이익 (한화시스템·LIG넥스원)",
        "title": "미국의 중국산 드론 공급망 차단 및 한국산 15% 예외 관세 적용에 따른 안티드론/전술통신 반사 수혜",
        "date": today_str,
        "play_mode": "Domestic_Alternative_Play",
        "background": (
            "[뉴스] 트럼프 미국 대통령, 외국산 드론 및 드론 부품에 최대 100% 징벌적 관세 부과 조치 발표 (한국산은 15% 관세 우대). 한화시스템-TTA AI 기반 5G 전술통신체계 공동 개발.\n"
            "Proxy: 미 국방/공공 드론 시장 내 비(非)중국산 대체 공급망 점유율 급증"
        ),
        "causal_chain": (
            "미국 드론 100% 관세 부과 행정명령 → 중국산 드론/부품 미국 및 우방국 시장 이탈 → 한국산 15% 관세 우대 및 AI 전술통신/안티드론 시스템 반사 수혜 → 한화시스템/LIG넥스원 무인체계 및 감시 센서 수주 폭증 → 영업이익 급증"
        ),
        "total_score": 91,
        "directness": 24,
        "leverage": 23,
        "scalability_or_rotation": 22,
        "technical_alignment": 22,
        "directness_reason": "미국의 100% 징벌적 관세 부과는 한국 드론/방산 무인체계 기업의 북미 점유율 상승과 직접 직결",
        "leverage_reason": "중국산 저가 드론의 퇴출로 높은 판가(ASP) 형성 및 한국 방산 부품의 이익 마진 확대",
        "scalability_or_rotation_reason": "지정학적 리스크 심화 속에 드론 및 안티드론, 전술통신 수요의 구조적 장기 성장",
        "technical_alignment_reason": "방산주 신고가 눌림목 구간에서 추가 상승 모멘텀 확보",
        "market_timing": "3-6개월",
        "critical_risk": "미국 자체 드론 제조 보조금 집행 속도 지연 및 우크라이나/중동 휴전 가능성",
        "raw_json": {
            "evidence_score": 18,
            "surprise_level": "Medium",
            "root_driver": "미국의 중국산 드론 100% 관세 부과 및 동맹국(한국 15%) 공급망 우대 정책 (Policy / Trade Regulation)",
            "prior_belief": "드론 및 부품 시장은 중국산의 가격 장벽으로 인해 한국 방산기업의 점유율 확대가 어렵다.",
            "posterior_belief": "미국의 100% 관세 장벽이 중국산 드론을 차단하면서, 15% 우대 관세를 받는 한국산 방산 무인체계 및 전술통신 장비의 미국 내 점유율이 폭증한다.",
            "revision_size": 85,
            "variant_view": {
                "consensus": "드론 관세 조치는 단기 뉴스 이벤트에 불과하다.",
                "my_view": "드론 및 안티드론은 현대전 및 공공 안보의 핵심이며, 100% 관세 장벽은 대체 불가능한 한국산 방산 무인체계의 미국 진출 가속화 계기가 된다."
            },
            "transmission_confidence": "High",
            "bottleneck_rank": ["Non-China Drone Supply Chain", "AI Tactical Communications"]
        },
        "candidates": [
            {"ticker": "272210", "name": "한화시스템", "role": "AI 기반 5G 전술통신망, 드론 감시·정찰 레이다 및 무인체계 핵심 공급자", "near_52w_high": 93.0, "ret_1m": 10.0, "ret_3m": 30.0, "early_signal_score": 93.0, "signal_flag": "🔺임박"},
            {"ticker": "079550", "name": "LIG넥스원", "role": "안티드론 시스템 및 드론용 유도무기 글로벌 안보 공급망 수혜", "near_52w_high": 91.0, "ret_1m": 7.0, "ret_3m": 25.0, "early_signal_score": 90.0, "signal_flag": "🟢관심"}
        ],
        "created_at": now_str
    }
]

print(f"3개 테마 매크로 가설({today_str}) Supabase 업로드 중...")

req_del = urllib.request.Request(f"{supabase_url}/rest/v1/macro_ideas?date=eq.{today_str}", headers=headers, method='DELETE')
try:
    with urllib.request.urlopen(req_del) as resp:
        print(f"기존 오늘 데이터 삭제 완료: status {resp.status}")
except Exception as e:
    print(f"기존 데이터 삭제 시도 중 (없거나 오류): {e}")

data_bytes = json.dumps(ideas, ensure_ascii=False).encode('utf-8')
req_ins = urllib.request.Request(f"{supabase_url}/rest/v1/macro_ideas", data=data_bytes, headers=headers, method='POST')
try:
    with urllib.request.urlopen(req_ins) as response:
        res_data = json.loads(response.read().decode('utf-8'))
        print(f"Supabase 성공적으로 업로드 완료! ({len(res_data)}개 테마 저장됨)")
        for idx, item in enumerate(res_data, 1):
            print(f" [{idx}] ID: {item.get('id')} | Theme: {item.get('theme')[:45]}... | Score: {item.get('total_score')}")
except urllib.error.HTTPError as e:
    print(f"Supabase 업로드 실패: {e}")
    print(f"Error body: {e.read().decode('utf-8')}")
except Exception as e:
    print(f"Supabase 업로드 실패: {e}")
