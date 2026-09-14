import json, subprocess, os
from dotenv import load_dotenv

load_dotenv('.env')

ideas = [
  {
    "theme": "원전/SMR",
    "title": "테라파워 SMR 상업용 건설 승인, 글로벌 원전 밸류체인 리레이팅 수혜",
    "date": "2026-07-18",
    "play_mode": "Global_Re_rating_Play",
    "background": "2026-07-17 자 뉴스(Nuclear startup TerraPower wins US approval to build commercial SMR plant)에 따르면 빌 게이츠가 설립한 테라파워가 미국 내 차세대 소형모듈원전 상업 건설 승인을 획득함. 또한 글로벌 노후 원전의 수명 연장(Refurbishment) 수요가 향후 5~10년간 원전 산업 성장을 주도할 전망. Oracle 등 빅테크의 AI 캐시번 및 투자 피크아웃 우려 속에서도 전력망 인프라는 확고한 성장세(Q)가 관측됨.",
    "causal_chain": "미국 내 SMR 상업용 건설 본격화 및 기존 원전 수명연장 트렌드 지속 -> 국내 핵심 기기 및 원전 설계 시공 밸류체인의 해외 수주 확대(Q 증가) -> 고정비 비중이 높은 플랜트 산업 특성상 본격적인 영업레버리지 발생(P 상승 및 마진 개선)",
    "total_score": 85,
    "directness": 20,
    "leverage": 25,
    "scalability_or_rotation": 25,
    "technical_alignment": 15,
    "directness_reason": "해외 원전 건설 및 SMR 승인은 핵심 부품사의 직수주로 직결",
    "leverage_reason": "장기 인프라 프로젝트의 특성상 고정비 레버리지 효과가 극대화됨",
    "scalability_or_rotation_reason": "AI 시대 폭증하는 전력수요를 뒷받침할 글로벌 차원의 확장성 보유",
    "technical_alignment_reason": "비에이치아이 등 핵심 부품사들이 신고가 부근(89.0%) 임박 시그널",
    "market_timing": "AI 섹터의 일시적 피크아웃 논란 속 자본이 유입될 대체 테마",
    "critical_risk": "건설 장기화 리스크, 친환경 단체 반발 및 정치적 불확실성",
    "candidates": [
      {
        "ticker": "083650",
        "name": "비에이치아이",
        "role": "대장주",
        "near_52w_high": 89.0,
        "ret_1m": 6.9,
        "ret_3m": 35.8,
        "early_signal_score": 56.9,
        "signal_flag": "🔺임박"
      },
      {
        "ticker": "034020",
        "name": "두산에너빌리티",
        "role": "밸류체인",
        "near_52w_high": 51.1,
        "ret_1m": -30.0,
        "ret_3m": -35.8,
        "early_signal_score": 20.0,
        "signal_flag": "🔵하단"
      },
      {
        "ticker": "052690",
        "name": "한전기술",
        "role": "밸류체인",
        "near_52w_high": 47.6,
        "ret_1m": -32.2,
        "ret_3m": -49.3,
        "early_signal_score": 20.0,
        "signal_flag": "🔵하단"
      }
    ],
    "raw_json": {}
  },
  {
    "theme": "해상풍력/전력기기",
    "title": "3.4조 규모 신안우이 해상풍력 착공, 하부구조물 및 전력망 밸류체인 실적 가시화",
    "date": "2026-07-18",
    "play_mode": "Domestic_Alternative_Play",
    "background": "2026-07-17 뉴스(국민성장펀드 1호 '신안우이 해상풍력' 첫삽)에 따르면 총 3조 4000억원, 390MW 규모의 신안우이 해상풍력이 파일 공사를 시작함. 2029년 상업 운전을 목표로 하부구조물(Jacket) 및 해저케이블 발주가 본격화. 이는 외국 자본 없이 순수 국내 자본으로 진행되는 최대 해상풍력 인프라 사업으로 전력기기 쇼티지와 맞물려 강한 시너지가 예상됨.",
    "causal_chain": "신안우이 해상풍력 착공 -> 국내 해저케이블 및 하부구조물(타워) 핵심 벤더 수주 물량 확대(Q 증가) -> 해상풍력 특성상 고부가 전력망 인프라 납품(P 상승) -> 수주 잔고 기반 중장기 마진 수혜",
    "total_score": 90,
    "directness": 25,
    "leverage": 20,
    "scalability_or_rotation": 20,
    "technical_alignment": 25,
    "directness_reason": "명확한 3.4조원 규모의 프로젝트 착공으로 관련 밸류체인 직수주 발생",
    "leverage_reason": "전력기기 쇼티지 국면에서 가격 전가력 극대화(P 상승 효과)",
    "scalability_or_rotation_reason": "전력 인프라는 현재 시장의 주도 테마로 지속적 순환매 가능성 큼",
    "technical_alignment_reason": "대한전선, LS마린솔루션, LS 모두 돌파 직후(100%) 강한 모멘텀",
    "market_timing": "본격 착공이 개시된 초입 국면",
    "critical_risk": "REC 단가 하락 가능성 및 인허가 과정의 예상치 못한 지연",
    "candidates": [
      {
        "ticker": "001440",
        "name": "대한전선",
        "role": "대장주",
        "near_52w_high": 100.0,
        "ret_1m": 96.5,
        "ret_3m": 91.5,
        "early_signal_score": 39.3,
        "signal_flag": "✅돌파직후"
      },
      {
        "ticker": "060370",
        "name": "LS마린솔루션",
        "role": "대장주",
        "near_52w_high": 100.0,
        "ret_1m": 33.5,
        "ret_3m": 27.4,
        "early_signal_score": 55.0,
        "signal_flag": "✅돌파직후"
      },
      {
        "ticker": "006260",
        "name": "LS",
        "role": "밸류체인",
        "near_52w_high": 100.0,
        "ret_1m": 71.3,
        "ret_3m": 97.8,
        "early_signal_score": 36.1,
        "signal_flag": "✅돌파직후"
      }
    ],
    "raw_json": {}
  },
  {
    "theme": "조선/에너지 인프라",
    "title": "중동 확전 양상 속 에너지 안보 우려, 韓 조선사 고부가가치 에너지 운반선 싹쓸이",
    "date": "2026-07-18",
    "play_mode": "Global_Re_rating_Play",
    "background": "2026-07-17 자 브렌트유가 90달러에 육박하며 미/이란 확전 양상에 따른 에너지 수급 불안이 심화(News 97). 헤지펀드들의 유가 롱 배팅이 10년래 최고치(News 90). 이런 가운데 'Korean shipbuilders sweep up LNG, ammonia orders' 뉴스(37)에서 보듯 글로벌 에너지 안보 확보를 위한 LNG/암모니아선 수주가 한국 대형 3사에 집중되고 있음.",
    "causal_chain": "중동 분쟁 장기화로 해상 에너지 운송 수요 폭증 -> LNG 및 암모니아 운반선 신조 발주 급증(Q 증가) -> 조선사 도크 풀방에 따른 선가 협상력 절대 우위(P 극대화) -> 두자릿수 영업이익률 달성(마진 턴어라운드)",
    "total_score": 80,
    "directness": 20,
    "leverage": 25,
    "scalability_or_rotation": 20,
    "technical_alignment": 15,
    "directness_reason": "글로벌 지정학 갈등이 운송 수단(선박) 발주로 즉각 이어지는 국면",
    "leverage_reason": "선가 상승(P) 시 건조 비용은 고정되므로 마진 래버리지가 막대함",
    "scalability_or_rotation_reason": "에너지 안보 확보는 단발성이 아닌 다년간 지속될 거시적 메가트렌드",
    "technical_alignment_reason": "조선사 주가가 하단(20점)에 머물러 있어 저가 매수 타이밍 유리",
    "market_timing": "조선 사이클 초입 및 실적 턴어라운드 원년",
    "critical_risk": "글로벌 경기 침체로 인한 전체 물동량 감소 및 철강 후판 가격 상승 압력",
    "candidates": [
      {
        "ticker": "009540",
        "name": "HD한국조선해양",
        "role": "대장주",
        "near_52w_high": 73.8,
        "ret_1m": -15.9,
        "ret_3m": -15.6,
        "early_signal_score": 20.0,
        "signal_flag": "🔵하단"
      },
      {
        "ticker": "010140",
        "name": "삼성중공업",
        "role": "밸류체인",
        "near_52w_high": 66.9,
        "ret_1m": -19.0,
        "ret_3m": -6.1,
        "early_signal_score": 20.0,
        "signal_flag": "🔵하단"
      },
      {
        "ticker": "042660",
        "name": "한화오션",
        "role": "밸류체인",
        "near_52w_high": 57.8,
        "ret_1m": -30.7,
        "ret_3m": -33.3,
        "early_signal_score": 20.0,
        "signal_flag": "🔵하단"
      }
    ],
    "raw_json": {}
  }
]

with open('ideas.json', 'w', encoding='utf-8') as f:
    json.dump(ideas, f, ensure_ascii=False, indent=2)

proc = subprocess.run(
    ["uv", "run", "python", "macro_ideas_save.py"],
    input=json.dumps(ideas, ensure_ascii=False),
    text=True, capture_output=True, encoding="utf-8"
)
print("STDOUT:", proc.stdout)
print("STDERR:", proc.stderr)
