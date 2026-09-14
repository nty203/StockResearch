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
            "→ 로봇 부품사 및 소프트웨어 기업들의 구조적 흑자 전환."
        ),
        "total_score": 90,
        "directness": 24,
        "leverage": 23,
        "scalability_or_rotation": 23,
        "technical_alignment": 20,
        "directness_reason": "대기업의 B2B/B2C 로봇 양산은 국내 부품 밸류체인 수주로 즉각 연결됨.",
        "leverage_reason": "양산 돌입 시 고정비 레버리지 효과로 폭발적 이익 성장이 가능.",
        "scalability_or_rotation_reason": "소프트웨어에서 하드웨어로 자금이 순환매되는 초기 국면.",
        "technical_alignment_reason": "현대오토에버, 로보티즈 등이 하방을 다지며 턴어라운드 조짐.",
        "market_timing": "하드웨어(로봇)가 새로운 투자 대안으로 떠오르는 최적의 타이밍.",
        "critical_risk": "글로벌 기업들의 CAPEX 이연 가능성.",
        "raw_json": {},
        "candidates": [
            {"ticker": "307950", "name": "현대오토에버", "role": "로봇SW플랫폼", "near_52w_high": 89.2, "ret_1m": 18.7, "ret_3m": -2.4, "early_signal_score": 65.0, "signal_flag": "🔺임박"},
            {"ticker": "108490", "name": "로보티즈", "role": "자율주행로봇", "near_52w_high": 80.7, "ret_1m": 10.3, "ret_3m": 9.9, "early_signal_score": 40.3, "signal_flag": "📌중기후보"}
        ],
        "created_at": now_str
    },
    {
        "theme": "전자부품/AI기판",
        "title": "첨단기술 육성 정책 및 반도체 업황 회복 기대감에 따른 AI 후공정/기판 업체 턴어라운드 가설",
        "date": today_str,
        "play_mode": "Global_Re_rating_Play",
        "background": (
            "[뉴스] KIST 30주년 첨단기술 육성 / 반도체, AI 효과로 회복세 뚜렷. "
            "정부 차원의 R&D 지원 확대와 글로벌 AI 수요 폭증으로 국내 반도체 패키징 및 유리기판 등 차세대 전자부품 생태계의 낙수효과 가시화."
        ),
        "causal_chain": (
            "글로벌 AI 반도체 수요 및 정부 지원책 가동 → FC-BGA, 유리기판 및 후공정 장비 수주 확대 (Q 증가) "
            "→ 차세대 첨단 패키징 스펙 요구에 따른 공급 단가(ASP) 프리미엄 유지 (P 상승) "
            "→ 소부장 업체들의 가동률 상승 및 영업이익률 V자 반등."
        ),
        "total_score": 86,
        "directness": 22,
        "leverage": 23,
        "scalability_or_rotation": 21,
        "technical_alignment": 20,
        "directness_reason": "AI 반도체 수요는 필수적으로 고다층 기판(FC-BGA) 및 어드밴스드 패키징 수요를 견인.",
        "leverage_reason": "가동률 회복 시 영업 레버리지가 매우 높음.",
        "scalability_or_rotation_reason": "HBM 이후 차세대 모멘텀인 유리기판 등 신기술 패러다임 변화.",
        "technical_alignment_reason": "삼성전기 등 주요 기판 업체들의 실적 바닥 통과.",
        "market_timing": "HBM 관련주 급등에 따른 밸류에이션 부담을 피하는 대안처.",
        "critical_risk": "IT 세트 수요 회복 지연 리스크.",
        "raw_json": {},
        "candidates": [
            {"ticker": "009150", "name": "삼성전기", "role": "FC-BGA/유리기판대장", "near_52w_high": 75.0, "ret_1m": 4.5, "ret_3m": -5.0, "early_signal_score": 50.0, "signal_flag": "📌중기후보"},
            {"ticker": "222800", "name": "심텍", "role": "메모리기판턴어라운드", "near_52w_high": 65.0, "ret_1m": 7.0, "ret_3m": -2.0, "early_signal_score": 48.0, "signal_flag": "📌중기후보"}
        ],
        "created_at": now_str
    },
    {
        "theme": "바이오/제약",
        "title": "금리 인하 가시화 및 하반기 핵심 임상/FDA 파이프라인 모멘텀 랠리 가설",
        "date": today_str,
        "play_mode": "Global_Re_rating_Play",
        "background": (
            "[뉴스] 물가 둔화세 뚜렷하며 금리 인하 기대감 확산 / K-바이오 주요 신약 임상 순항. "
            "거시적으로 금리 인하 사이클이 다가오며 펀딩/연구개발(R&D) 비용 부담이 큰 바이오텍의 밸류에이션 리레이팅 환경이 조성됨. "
            "여기에 하반기 FDA 승인 대기 파이프라인과 글로벌 학회(ESMO 등) 모멘텀이 맞물리는 중."
        ),
        "causal_chain": (
            "매크로(금리 인하) 및 마이크로(핵심 파이프라인 성과) 동시 개선 → 기술수출(L/O) 계약 체결 및 글로벌 빅파마와의 파트너십 가속 "
            "→ 마일스톤 유입으로 인한 펀더멘털 개선 및 파이프라인 가치 상향 조정 "
            "→ 섹터 전반의 강력한 순환매 장세 도래."
        ),
        "total_score": 88,
        "directness": 22,
        "leverage": 24,
        "scalability_or_rotation": 24,
        "technical_alignment": 18,
        "directness_reason": "기술수출 및 FDA 승인은 즉각적인 실적(마일스톤)으로 연결됨.",
        "leverage_reason": "신약 개발 성공 시 이익률은 기하급수적으로 팽창.",
        "scalability_or_rotation_reason": "상반기 전력/반도체 주도장 이후, 금리 인하 수혜주로 강력한 자금 순환매 기대.",
        "technical_alignment_reason": "유한양행, 알테오젠 등 대형 바이오주들이 신고가 트라이 중.",
        "market_timing": "금리 인하 시그널이 명확해지는 현 시점이 바이오 섹터 비중 확대의 적기.",
        "critical_risk": "임상 실패 또는 FDA 승인 지연이라는 고유의 불확실성 리스크.",
        "raw_json": {},
        "candidates": [
            {"ticker": "000100", "name": "유한양행", "role": "레이저티닙FDA/신약대장", "near_52w_high": 92.0, "ret_1m": 15.5, "ret_3m": 30.2, "early_signal_score": 85.0, "signal_flag": "✅돌파직후"},
            {"ticker": "196170", "name": "알테오젠", "role": "SC제형/플랫폼대장", "near_52w_high": 95.0, "ret_1m": -2.0, "ret_3m": 45.0, "early_signal_score": 80.0, "signal_flag": "🔺임박"}
        ],
        "created_at": now_str
    },
    {
        "theme": "조선/방산",
        "title": "K-조선 슈퍼사이클 재점화 및 노후선박 교체 사이클에 따른 실적 우상향 가설",
        "date": today_str,
        "play_mode": "Global_Re_rating_Play",
        "background": (
            "[뉴스] 글로벌 환경규제 강화와 선가 지속 상승 / K-방산 수출 호조세 이어져. "
            "조선업의 신조선가가 사상 최고치를 경신 중이며, 친환경 선박(LNG, 메탄올 추진선) 중심의 선별 수주 효과로 조선사들의 구조적 흑자 폭이 확대됨."
        ),
        "causal_chain": (
            "도크(Dock) 풀 케파 확정 및 제한된 공급 → 고부가가치 선박 위주의 선별 수주 및 선가(P) 지속 상승 "
            "→ 강재가 안정화와 환율 효과까지 겹침 → 영업이익률의 구조적 레벨업."
        ),
        "total_score": 84,
        "directness": 23,
        "leverage": 20,
        "scalability_or_rotation": 21,
        "technical_alignment": 20,
        "directness_reason": "선가 상승과 환율 효과가 고스란히 이익으로 직결됨.",
        "leverage_reason": "고정비 비중이 큰 중공업 특성상 손익분기점(BEP) 돌파 이후의 마진율 스프레드가 큼.",
        "scalability_or_rotation_reason": "AI/테크 피로감 속에서 확실한 실적주로의 피난처 역할 수행.",
        "technical_alignment_reason": "HD한국조선해양, 삼성중공업 등 주요 종목 우상향 추세 견고.",
        "market_timing": "하반기 본격적인 실적 턴어라운드를 숫자로 확인하며 들어갈 수 있는 구간.",
        "critical_risk": "후판 가격 급등이나 글로벌 경기 침체로 인한 물동량 감소.",
        "raw_json": {},
        "candidates": [
            {"ticker": "010140", "name": "삼성중공업", "role": "흑자전환대장/FLNG", "near_52w_high": 90.0, "ret_1m": 8.5, "ret_3m": 18.0, "early_signal_score": 75.0, "signal_flag": "🔺임박"},
            {"ticker": "093220", "name": "HD한국조선해양", "role": "조선지주/실적호조", "near_52w_high": 88.0, "ret_1m": 5.0, "ret_3m": 12.0, "early_signal_score": 65.0, "signal_flag": "🔺임박"}
        ],
        "created_at": now_str
    },
    {
        "theme": "음식료/수출소비재",
        "title": "K-푸드 글로벌 침투율 폭발 및 북미/유럽 수출 퀀텀점프 가설",
        "date": today_str,
        "play_mode": "Global_Re_rating_Play",
        "background": (
            "[뉴스] 라면 수출액 월간 사상 최고치 경신 / 삼양식품, 북미 주류 채널 입점 가속. "
            "SNS 바이럴(불닭볶음면, 냉동김밥 등)을 시작으로 한 K-푸드의 인기가 단순 유행을 넘어 서구권 메인스트림 유통 채널(월마트, 코스트코 등) 입점으로 이어지며 구조적 성장기에 진입함."
        ),
        "causal_chain": (
            "글로벌 인지도 상승 및 메인 유통채널 입점 → 수출 물량(Q) 폭증 및 고마진 수출 비중 확대 "
            "→ 원가 안정화 속 마진 믹스 개선 (ASP 상승 효과) → 음식료 기업들의 글로벌 밸류에이션(PER 20배 이상) 리레이팅."
        ),
        "total_score": 93,
        "directness": 25,
        "leverage": 23,
        "scalability_or_rotation": 22,
        "technical_alignment": 23,
        "directness_reason": "매월 발표되는 관세청 수출 데이터로 실적 서프라이즈를 즉각적으로 검증 가능.",
        "leverage_reason": "국내 라인 증설 및 가동률 100% 돌파로 단위당 고정비가 급감하며 영업이익률 20% 돌파.",
        "scalability_or_rotation_reason": "아시아를 넘어 미국, 유럽 등 선진국 시장으로 확장 중.",
        "technical_alignment_reason": "삼양식품 등 대장주의 독보적인 신고가 랠리 및 빙그레, 농심 등 후발주 동참.",
        "market_timing": "환율 효과와 함께 실적이 매달 찍히는 가장 확실한 모멘텀 구간.",
        "critical_risk": "곡물가 인플레이션 재발 또는 K-푸드 유행의 단기 소멸 우려.",
        "raw_json": {},
        "candidates": [
            {"ticker": "003230", "name": "삼양식품", "role": "K푸드대장/수출폭발", "near_52w_high": 98.0, "ret_1m": 22.0, "ret_3m": 85.0, "early_signal_score": 88.0, "signal_flag": "✅돌파직후"},
            {"ticker": "005180", "name": "빙그레", "role": "아이스크림수출/여름수혜", "near_52w_high": 92.0, "ret_1m": 12.0, "ret_3m": 35.0, "early_signal_score": 75.0, "signal_flag": "🔺임박"}
        ],
        "created_at": now_str
    },
    {
        "theme": "금융/밸류업",
        "title": "하반기 밸류업 지수 편입 및 자사주 소각 등 주주환원율 퀀텀점프 가설",
        "date": today_str,
        "play_mode": "Global_Re_rating_Play",
        "background": (
            "[뉴스] 한국거래소 밸류업 지수 하반기 출범 예고 / 주요 금융지주, 분기 배당 및 2천억 규모 자사주 매입 발표. "
            "정부의 '기업 밸류업 프로그램'이 세제 지원 등 구체적 인센티브와 함께 본격 궤도에 오르며, "
            "자본 여력이 충분한 은행/금융지주를 중심으로 글로벌 스탠다드 수준의 주주환원(ROE 제고)이 시작됨."
        ),
        "causal_chain": (
            "밸류업 정책 인센티브 구체화 및 지수(ETF) 출시 대기 → 연기금 및 글로벌 패시브 자금의 저PBR 가치주 비중 확대 (수급 개선) "
            "→ 금융지주들의 역대급 실적 기반 자사주 소각/분기배당 확대 (주당가치 상승) "
            "→ 만성적인 '코리아 디스카운트' 해소 및 섹터 전체의 PBR 리레이팅."
        ),
        "total_score": 85,
        "directness": 22,
        "leverage": 18,
        "scalability_or_rotation": 25,
        "technical_alignment": 20,
        "directness_reason": "하반기 밸류업 지수 발표 및 연계 패시브 자금 집행 스케줄이 명확함.",
        "leverage_reason": "이익 레버리지는 낮으나 자사주 소각으로 인한 유통주식수 감소가 주당순이익(EPS)을 즉시 끌어올림.",
        "scalability_or_rotation_reason": "성장주(AI) 고점 논란 발생 시 시장의 거대한 자금이 쉴 수 있는 가장 안전하고 강력한 배당 피난처.",
        "technical_alignment_reason": "KB금융, 메리츠금융지주 등 밸류업 주도주들의 52주 신고가 근접 및 정배열 추세 지속.",
        "market_timing": "하반기 지수 런칭 및 연말 배당 시즌을 앞두고 기관 매수세가 가속화되는 길목.",
        "critical_risk": "부동산 PF 연착륙 실패에 따른 대규모 대손충당금 적립 리스크 및 정책 후퇴 가능성.",
        "raw_json": {},
        "candidates": [
            {"ticker": "105560", "name": "KB금융", "role": "밸류업대장/주주환원", "near_52w_high": 95.0, "ret_1m": 8.5, "ret_3m": 15.0, "early_signal_score": 82.0, "signal_flag": "🔺임박"},
            {"ticker": "138040", "name": "메리츠금융지주", "role": "자사주소각/배당성향최상", "near_52w_high": 97.0, "ret_1m": 12.0, "ret_3m": 25.0, "early_signal_score": 85.0, "signal_flag": "✅돌파직후"}
        ],
        "created_at": now_str
    }
]

print(f"6개 테마 매크로 가설({today_str}) Supabase 업로드 중...")

# Delete today's ideas first just in case
req_del = urllib.request.Request(f"{supabase_url}/rest/v1/macro_ideas?date=eq.{today_str}", headers=headers, method='DELETE')
try:
    urllib.request.urlopen(req_del)
except:
    pass

# Insert the 6 new themes
url = f"{supabase_url}/rest/v1/macro_ideas"
req = urllib.request.Request(url, data=json.dumps(ideas).encode('utf-8'), headers=headers, method='POST')

try:
    with urllib.request.urlopen(req) as response:
        if response.getcode() in [200, 201]:
            print(f"성공적으로 {len(ideas)}개의 매크로 테마가 DB에 반영되었습니다.")
        else:
            print(f"Status code: {response.getcode()}")
except Exception as e:
    print("Error:", e)
    if hasattr(e, 'read'):
        print(e.read().decode('utf-8'))
