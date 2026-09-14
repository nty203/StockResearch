import os
import sys
import json
import urllib.request
import urllib.parse
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

# Set stdout to utf-8 to prevent encoding issues on Windows
sys.stdout.reconfigure(encoding='utf-8')

# Load .env
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

# Determine Korea Standard Time (KST, UTC+9) date
kst = timezone(timedelta(hours=9))
today_str = datetime.now(kst).strftime("%Y-%m-%d")
now_str = datetime.now(timezone.utc).isoformat()

ideas = [
    {
        "theme": "로봇/피지컬AI",
        "title": "LG전자-엔비디아 로봇 연합 결성 및 피지컬 AI 본격화에 따른 지능형 제조 솔루션 및 부품사 리레이팅 가설",
        "date": today_str,
        "play_mode": "Global_Re_rating_Play",
        "background": (
            "[뉴스] 엔비디아와 로봇동맹 LG전자, 피지컬AI 사업화에 운명 건다 (2026-07-08). "
            "LG전자가 엔비디아와 협력하여 로봇용 피지컬 AI 플랫폼 구축 및 지능형 생산 솔루션 글로벌 시장 공략에 착수. "
            "하드웨어 제조 역량과 AI 컴퓨팅 리더십의 결합으로 로봇 부품 및 플랫폼 산업의 질적 도약 발판 마련."
        ),
        "causal_chain": (
            "LG전자-엔비디아 로봇 동맹 및 피지컬 AI 상용화 개시 → 지능형 생산 라인 구축을 위한 로봇 공급 체인 활성화 (Q 증가) "
            "→ 센서, 감속기, 관절 모듈 등 핵심 부품사들의 기술 장벽 우위 및 선제적 단가 협상력 확보 (P 상승) "
            "→ 지능형 로봇 밸류체인 참여 기업들의 실적 리레이팅."
        ),
        "total_score": 86,
        "directness": 23,
        "leverage": 21,
        "scalability_or_rotation": 24,
        "technical_alignment": 18,
        "directness_reason": "글로벌 톱티어 GPU 기업인 엔비디아와 가전/생산 최강자인 LG전자의 협력은 부품 및 자율주행 소프트웨어 수요 확대로 직결됨.",
        "leverage_reason": "로봇 관절 및 감속기, 물류 소프트웨어는 연구개발 고정비 비중이 크며, 대량 생산 및 수주 시 영업 레버리지가 급격히 확대됨.",
        "scalability_or_rotation_reason": "생산 자동화 수요가 글로벌 전역의 공장(스마트 팩토리)과 물류센터로 확장되고 있어 장기적인 순환매 매력이 존재함.",
        "technical_alignment_reason": "현대오토에버(52w 89.2%, 1M 18.7%), 로보티즈(52w 80.7%, 1M 10.3%) 등 협업 수혜주들의 모멘텀 개선세 뚜렷.",
        "market_timing": "IT 하드웨어 주도주의 피크아웃 우려 속에서 신성장 동력으로서의 피지컬 AI 실체화 뉴스는 수급 로테이션의 훌륭한 촉매제.",
        "critical_risk": "글로벌 경기 둔화에 따른 대기업 설비투자(CAPEX) 집행 지연 및 AI 로봇의 기술적 완성도 검증 장기화.",
        "raw_json": {},
        "candidates": [
            {"ticker": "307950", "name": "현대오토에버", "role": "피지컬AI/자율주행SW", "near_52w_high": 89.2, "ret_1m": 18.7, "ret_3m": -2.4, "early_signal_score": 65.0, "signal_flag": "🔺임박"},
            {"ticker": "108490", "name": "로보티즈", "role": "LG전자지분보유협업", "near_52w_high": 80.7, "ret_1m": 10.3, "ret_3m": 9.9, "early_signal_score": 40.3, "signal_flag": "📌중기후보"},
            {"ticker": "056080", "name": "유진로봇", "role": "자율주행솔루션", "near_52w_high": 28.7, "ret_1m": -31.5, "ret_3m": -49.3, "early_signal_score": 20.0, "signal_flag": "🔵하단"},
            {"ticker": "066570", "name": "LG전자", "role": "엔비디아로봇동맹대장", "near_52w_high": 48.2, "ret_1m": -23.8, "ret_3m": 62.0, "early_signal_score": 19.0, "signal_flag": "🔵하단"}
        ],
        "created_at": now_str
    },
    {
        "theme": "원전/전력",
        "title": "테라파워 최초 상업용 SMR 와이오밍 건설 승인 및 한·미·일 원전 동맹 가속에 따른 글로벌 원자로 기자재 슈퍼사이클 가설",
        "date": today_str,
        "play_mode": "Global_Re_rating_Play",
        "background": (
            "[뉴스] Nuclear startup TerraPower wins US approval to build commercial SMR plant (2026-07-07) / "
            "한·미·일, 인도·태평양 지역 SMR 도입 가속화 협력 각서 체결 (2026-07-07). "
            "빌 게이츠의 테라파워가 미국 와이오밍주에서 최초의 상업용 SMR 건설 승인을 획득하고, 한미일 3국 정부가 인태 지역 SMR 도입 가속화 협력을 선언하며 글로벌 SMR 시장이 상용화 궤도에 진입."
        ),
        "causal_chain": (
            "미국 내 상업용 SMR 건설 승인 및 정부 차원의 도입 동맹 가속화 → 국내 SMR 주기기 및 보조 기자재 수주 물량 급증 (Q 증가) "
            "→ 원자력 발전 특화 MMIS 제어시스템 및 전선/전력망 자재의 글로벌 단가 상승 유지 (P 상승) "
            "→ 원전 관련 고정비 비중이 높은 설계 및 주기기 제조사들의 영업 레버리지 극대화."
        ),
        "total_score": 91,
        "directness": 25,
        "leverage": 23,
        "scalability_or_rotation": 24,
        "technical_alignment": 19,
        "directness_reason": "최초의 실질 상업 SMR 건설 승인 및 3국 정부 공동 동맹은 기자재 수주 가능성을 강력하게 뒷받침함.",
        "leverage_reason": "원전 주기기 제조 및 종합설계 분야는 높은 초기 연구설계 비용으로 인해 본격 수주 인식 시 가파른 이익 마진 확장이 나타남.",
        "scalability_or_rotation_reason": "인도·태평양 등 글로벌 인프라 개척과 함께 친환경 무탄소 전력원 확대로써 중장기 정책 확장성 보유.",
        "technical_alignment_reason": "대원전선우(52w 100%, 1M 53.6%)의 강력한 돌파와 함께 전력망 레버리지 주의 차별적 추세 형성.",
        "market_timing": "전력 부족이 구조화되는 국면에서 글로벌 정책 모멘텀과 상용화 실체가 결합하여 2차 주도주 랠리를 재점화하기 좋은 시점.",
        "critical_risk": "원전 안전 규제 강화에 따른 건설 일정 지연 리스크 및 지정학적 리스크(중동/이란 위협 등) 부각 가능성.",
        "raw_json": {},
        "candidates": [
            {"ticker": "006345", "name": "대원전선우", "role": "전선/전력망레버리지", "near_52w_high": 100.0, "ret_1m": 53.6, "ret_3m": 58.7, "early_signal_score": 55.0, "signal_flag": "✅돌파직후"},
            {"ticker": "034020", "name": "두산에너빌리티", "role": "SMR원자로제조대장", "near_52w_high": 59.8, "ret_1m": -11.6, "ret_3m": -19.4, "early_signal_score": 20.0, "signal_flag": "🔵하단"},
            {"ticker": "052690", "name": "한전기술", "role": "원전종합설계", "near_52w_high": 52.2, "ret_1m": -15.5, "ret_3m": -41.1, "early_signal_score": 20.0, "signal_flag": "🔵하단"},
            {"ticker": "032820", "name": "우리기술", "role": "SMR MMIS제어시스템", "near_52w_high": 37.1, "ret_1m": -20.8, "ret_3m": -54.0, "early_signal_score": 20.0, "signal_flag": "🔵하단"},
            {"ticker": "267260", "name": "HD현대일렉트릭", "role": "초고압변압기대장주", "near_52w_high": 63.3, "ret_1m": -4.8, "ret_3m": -8.3, "early_signal_score": 20.0, "signal_flag": "🔵하단"}
        ],
        "created_at": now_str
    },
    {
        "theme": "내수소비/유통/명품",
        "title": "2030 주도의 소주 소비 트렌드 변화 및 K-푸드 글로벌 대형 유통망 침투 확대에 따른 가공식품 이익 성장 가설",
        "date": today_str,
        "play_mode": "Domestic_Alternative_Play",
        "background": (
            "[뉴스] 회식 줄었는데 소주는 더 팔렸다…요즘 2030 달려가는 곳 (2026-07-08) / "
            "식음료·건강·뷰티 3대 영역 최대 20% 할인 혜택 등 유통사 연동 확대. "
            "2030 세대의 프리미엄 요리 주점 및 홈술 문화 결합으로 국내 소주 등 주류 소비 패러다임이 변화하고, 삼양식품/농심 등 주요 가공식품사들의 글로벌 유통 채널 확장 효과 지속."
        ),
        "causal_chain": (
            "2030의 주류 소비 재활성화 및 글로벌 유통 채널 점유율 상승 → 주류 및 수출용 라면/과자 출하량 상승 (Q 증가) "
            "→ 원자재 가격(밀가루, 전분 등) 하향 안정세 속 수출 판가 프리미엄 유지 (P 상승) "
            "→ 음식료/소비재 업체들의 가동률 개선에 따른 스프레드 및 영업마진율 회복."
        ),
        "total_score": 81,
        "directness": 22,
        "leverage": 20,
        "scalability_or_rotation": 22,
        "technical_alignment": 17,
        "directness_reason": "소비 데이터 개선 및 수출 실적 수치가 직접적으로 매출 및 영업이익 증대로 환원됨.",
        "leverage_reason": "원자재 스프레드가 확대되는 상황에서 공장 가동률이 유지되어 원가 절감에 따른 이익 개선 속도가 빠름.",
        "scalability_or_rotation_reason": "라면에서 스낵, 주류 등으로 품목이 다양화되고 글로벌 대형 할인점으로의 지속적 매대 확보로 확장성이 큼.",
        "technical_alignment_reason": "오리온(52w 95.5%, 1M 5.0%), 삼양식품(52w 82.3%, 1M 5.3%) 등 주요 바스켓 종목들의 완만하지만 견조한 상승 추세 진입.",
        "market_timing": "기술주 변동성 국면에서 강한 방어력과 글로벌 성장을 겸비한 필수소비재로 순환 수급 유입이 용이함.",
        "critical_risk": "해외 현지 위생 및 통관 규제 강화, 환율 급락에 따른 원화 환산 수출 마진 축소 가능성.",
        "raw_json": {},
        "candidates": [
            {"ticker": "271560", "name": "오리온", "role": "글로벌제과수출", "near_52w_high": 95.5, "ret_1m": 5.0, "ret_3m": 7.3, "early_signal_score": 55.0, "signal_flag": "🔺임박"},
            {"ticker": "003230", "name": "삼양식품", "role": "글로벌K푸드라면수출대장", "near_52w_high": 82.3, "ret_1m": 5.3, "ret_3m": 13.6, "early_signal_score": 35.3, "signal_flag": "📌중기후보"},
            {"ticker": "000080", "name": "하이트진로", "role": "내수소주1위/2030요새", "near_52w_high": 78.1, "ret_1m": 2.7, "ret_3m": -4.4, "early_signal_score": 22.7, "signal_flag": "🔵하단"},
            {"ticker": "004370", "name": "농심", "role": "글로벌라면수출2위", "near_52w_high": 69.7, "ret_1m": -2.9, "ret_3m": -2.0, "early_signal_score": 20.0, "signal_flag": "🔵하단"}
        ],
        "created_at": now_str
    },
    {
        "theme": "2차전지/ESS",
        "title": "LG에너지솔루션 2분기 영업이익 흑자 달성 및 친환경 모빌리티 부품 다변화에 따른 전장 배터리·소재 회복 가설",
        "date": today_str,
        "play_mode": "Domestic_Alternative_Play",
        "background": (
            "[뉴스] 적자 탈출한 LG엔솔, 2분기 영업익 1133억원 (2026-07-07) / "
            "시노펙스, 베트남 공장에 150억원 추가 투자...전기차용 FPCB 공급 가시화 (2026-07-07). "
            "전기차 캐즘 장기화 우려 속에서도 LG에너지솔루션이 2분기 흑자 기조를 회복하며 바닥을 확인하였으며, 주요 전장 협력업체들이 베트남 투자를 늘려 전기차 및 ESS용 부품 대량 양산에 착수."
        ),
        "causal_chain": (
            "대형 제조사의 실적 턴어라운드 및 전장 부품 국산화/공급처 다변화 → 친환경 모빌리티 및 ESS 부품 수주 확대 (Q 증가) "
            "→ 배터리 판가 안정화 및 고부가 스펙 위주 고정 단가 유지 (P 안정) "
            "→ 2차전지 소재 및 전장 부품사들의 이익 스프레드 반등 및 가동률 회복."
        ),
        "total_score": 79,
        "directness": 21,
        "leverage": 19,
        "scalability_or_rotation": 21,
        "technical_alignment": 18,
        "directness_reason": "LG엔솔의 흑자 탈출은 배터리 공급망 전반의 생존 및 수주 연속성을 직접 방증함.",
        "leverage_reason": "소재 및 부품 업종은 리튬 가격 급락 안정화 이후 스프레드 개선 및 대량 수주에 따른 고정비 회수 효과 발생.",
        "scalability_or_rotation_reason": "전기차뿐만 아니라 에너지저장장치(ESS) 시장의 고성장으로 포트폴리오 다변화 확장 가능.",
        "technical_alignment_reason": "에코프로비엠(52w 87.8%, 1M -0.9%) 등 대표 하락 낙폭과대주의 중기 바닥 확인 신호 포착.",
        "market_timing": "악재(캐즘, 실적 쇼크)가 선반영된 낙폭 과대 상태에서 가시적 턴어라운드 데이터와 함께 저가 수급 유입에 유리한 국면.",
        "critical_risk": "주요국 선거에 따른 전기차 보조금 정책 폐지 혹은 감축 리스크, 글로벌 배터리 공급 과잉 장기화.",
        "raw_json": {},
        "candidates": [
            {"ticker": "247540", "name": "에코프로비엠", "role": "양극재제조대장", "near_52w_high": 87.8, "ret_1m": -0.9, "ret_3m": 1.2, "early_signal_score": 30.0, "signal_flag": "📌중기후보"},
            {"ticker": "025320", "name": "시노펙스", "role": "전기차FPCB베트남공급", "near_52w_high": 55.6, "ret_1m": 1.7, "ret_3m": -27.3, "early_signal_score": 21.7, "signal_flag": "🔵하단"},
            {"ticker": "373220", "name": "LG에너지솔루션", "role": "배터리제조대장/2Q흑자", "near_52w_high": 64.6, "ret_1m": -16.3, "ret_3m": -18.2, "early_signal_score": 20.0, "signal_flag": "🔵하단"},
            {"ticker": "006400", "name": "삼성SDI", "role": "배터리/ESS제조", "near_52w_high": 63.9, "ret_1m": -32.7, "ret_3m": 10.3, "early_signal_score": 20.0, "signal_flag": "🔵하단"}
        ],
        "created_at": now_str
    }
]

print(f"Supabase 연결 및 중복 제거 처리 중... (오늘 날짜: {today_str})")
for idea in ideas:
    theme = idea["theme"]
    # Delete existing idea for today and this theme
    delete_url = f"{supabase_url}/rest/v1/macro_ideas?date=eq.{today_str}&theme=eq.{urllib.parse.quote(theme)}"
    del_req = urllib.request.Request(delete_url, headers=headers, method='DELETE')
    try:
        with urllib.request.urlopen(del_req) as response:
            print(f"[{theme}] 기존 가설 삭제 성공 (Status: {response.getcode()})")
    except Exception as e:
        print(f"[{theme}] 기존 가설 삭제 실패 또는 없음: {e}")

# Insert new ideas
url = f"{supabase_url}/rest/v1/macro_ideas"
req = urllib.request.Request(url, data=json.dumps(ideas).encode('utf-8'), headers=headers, method='POST')

try:
    with urllib.request.urlopen(req) as response:
        print("Status code:", response.getcode())
        print("4 new ideas successfully saved/upserted to Supabase!")
except urllib.error.URLError as e:
    print("Error:", getattr(e, 'reason', e))
    if hasattr(e, 'read'):
        print(e.read().decode('utf-8'))
