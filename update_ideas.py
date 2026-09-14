import re

file_path = 'insert_today_ideas_v5.py'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

new_ideas_code = '''
ideas = [
    {
        "theme": "AIDC 전력 인프라 대격변 및 하이브리드 발전용 엔진(HD현대중공업) 1GW 수주 달성 (HD현대중공업·LS ELECTRIC)",
        "title": "HD현대중공업 美 코반에너지 9560억 발전용 엔진 계약 & LS일렉트릭 AI 데이터센터 DC 배전 협력",
        "date": today_str,
        "play_mode": "Global_Re_rating_Play",
        "background": (
            "[뉴스] HD현대중공업이 미국 에너지 인프라 개발기업 코반에너지그룹과 1GW 규모(9560억 원) '힘센엔진' 발전설비 공급계약을 체결.\\n"
            "LS일렉트릭이 GS건설과 AI 데이터센터용 직류(DC) 배전 기술 개발과 전력기기 공급에 협력.\\n"
            "전선 및 배터리 원자재인 구리와 코발트 가격이 남미 폭설과 콩고 수출금지로 단기 급등세 시현.\\n"
            "Proxy: AI 데이터센터 전력 확보를 위해 가스/디젤 엔진 발전 수요가 폭발적으로 급증, 직류 배전 도입 가속화."
        ),
        "causal_chain": (
            "AIDC 전력망 병목 현상 및 송전망 지연 → 유연한 분산 전원(발전용 엔진) 수요 폭증 "
            "→ HD현대중공업 대규모 북미 빅테크 수주 입증 → 전력 기기 및 인프라 업체 멀티플 리레이팅."
        ),
        "total_score": 95,
        "directness": 25,
        "leverage": 24,
        "scalability_or_rotation": 24,
        "technical_alignment": 22,
        "directness_reason": "HD현대중공업의 9560억원 단일 계약 공시와 LS일렉트릭-GS건설 협력으로 AIDC 전력 병목 수혜 직접 확인.",
        "leverage_reason": "육상 발전용 '힘센엔진'의 독과점적 지위와 높은 마진율.",
        "scalability_or_rotation_reason": "변압기/전선에서 발전 인프라(엔진, 가스터빈)로 전력 테마의 구조적 순환매 확산.",
        "technical_alignment_reason": "조선업 턴어라운드와 육상 발전 수주 모멘텀이 겹치며 주가 모멘텀 폭발 국면.",
        "market_timing": "북미 데이터센터발 대규모 자체 발전망 구축 사이클 돌입 (0-6개월).",
        "critical_risk": "에너지 가격 급등 또는 미국 환경 규제 변동.",
        "raw_json": {
            "evidence_score": 20,
            "surprise_level": "Large",
            "root_driver": "AIDC Power Bottleneck & Engine Generator Demand Boom",
            "transmission_confidence": "High",
            "bottleneck_rank": ["Large-scale Generator Engines", "DC Power Distribution", "Copper Supply"]
        },
        "candidates": [
            {"ticker": "329180", "name": "HD현대중공업", "role": "1GW(9560억) 규모 AIDC용 발전 엔진 수주 및 독과점 지위", "near_52w_high": 95.0, "ret_1m": 15.0, "ret_3m": 42.0, "early_signal_score": 96.0, "signal_flag": "🔺임박"},
            {"ticker": "010120", "name": "LS ELECTRIC", "role": "AI 데이터센터 직류(DC) 배전망 주도 및 변압기 숏티지 지속", "near_52w_high": 92.0, "ret_1m": 10.0, "ret_3m": 30.0, "early_signal_score": 92.0, "signal_flag": "📌중기후보"}
        ],
        "created_at": now_str
    },
    {
        "theme": "AI 서버용 고사양 부품(MLCC·FCBGA) 공급 부족 심화 및 디스플레이 폼팩터 진화 (삼성전기·LG디스플레이)",
        "title": "삼성전기 AI 서버용 MLCC 및 FCBGA 숏티지로 목표가 상향 & LG디스플레이 '5스택 OLED' 개발 검토",
        "date": today_str,
        "play_mode": "Supply_Chain_Play",
        "background": (
            "[뉴스] 하나증권은 삼성전기에 대해 AI 서버용 MLCC와 플립칩볼그리드어레이(FCBGA) 공급 부족으로 시장 기대를 웃도는 수익성을 낼 것이라며 목표가 300만원 유지.\\n"
            "LG디스플레이는 차세대 IT용으로 청색 3개, 적색·녹색 발광층 2개를 결합한 '5스택 OLED' 개발 검토 착수.\\n"
            "Proxy: AI 서버 출하량 증가로 탑재되는 고부가가치 MLCC 채용량이 급증하며, 기판 스펙 고도화로 공급사 제한."
        ),
        "causal_chain": (
            "AI 서버 고성능화 → 기판(FCBGA) 대면적화 및 MLCC 고온/고압 스펙 요구 → 범용 부품 대비 공급 제한 "
            "→ 하이엔드 부품 단가 상승 및 삼성전기 등 선도업체 마진 스프레드 확대."
        ),
        "total_score": 92,
        "directness": 24,
        "leverage": 23,
        "scalability_or_rotation": 22,
        "technical_alignment": 23,
        "directness_reason": "증권사 커버리지 분석을 통해 서버용 하이엔드 부품의 숏티지 및 실적 기여도 상승 확인.",
        "leverage_reason": "일부 글로벌 기업만이 AI 서버급 양산 수율을 확보.",
        "scalability_or_rotation_reason": "AI 투자가 반도체 코어 칩에서 기판, 패키징, 수동소자 등 하드웨어 밸류체인 전반으로 확산.",
        "technical_alignment_reason": "실적 추정치 상향 대비 밸류에이션 매력 존재, 기관 수급 유입 기대.",
        "market_timing": "AI 서버 빌드업 본격화 및 하반기 부품 재고 축적 사이클 (3-6개월).",
        "critical_risk": "PC 및 스마트폰 등 전방 IT 수요 회복 지연으로 인한 범용 부품 판가 하락.",
        "raw_json": {
            "evidence_score": 18,
            "surprise_level": "Medium",
            "root_driver": "AI Server Hardware Spec Upgrade & High-end Component Shortage",
            "transmission_confidence": "High",
            "bottleneck_rank": ["AI Server MLCC", "FCBGA for High-end Compute", "OLED IT Form Factor"]
        },
        "candidates": [
            {"ticker": "009150", "name": "삼성전기", "role": "AI 서버용 고부가가치 MLCC 및 FCBGA 공급 부족 수혜 대장주", "near_52w_high": 88.0, "ret_1m": 5.0, "ret_3m": 12.0, "early_signal_score": 91.0, "signal_flag": "📌중기후보"},
            {"ticker": "034220", "name": "LG디스플레이", "role": "차세대 5스택 OLED 등 IT 폼팩터 진화에 따른 턴어라운드 기대", "near_52w_high": 75.0, "ret_1m": 2.0, "ret_3m": -5.0, "early_signal_score": 82.0, "signal_flag": "👀관찰"}
        ],
        "created_at": now_str
    },
    {
        "theme": "K-방산·조선 지정학적 수혜 및 우주항공 거버넌스 강화 (한화시스템·한화오션)",
        "title": "한화그룹 KAI 지분 15% 이상 확보 및 기업결합심사 추진 & 지정학적 리스크 심화",
        "date": today_str,
        "play_mode": "Event_Driven_Play",
        "background": (
            "[뉴스] 한화시스템 등 한화그룹 계열사들이 최근 한 달간 장내에서 한국항공우주산업(KAI) 지분을 매입해 15% 이상 확보, 공정위에 기업결합심사 신청 예정.\\n"
            "호르무즈 해협 재개 협상 교착 등 중동 지정학적 리스크 심화로 국제유가 WTI 80달러대 진입 (5% 급등).\\n"
            "Proxy: 방산 통합 시너지를 위한 지배구조 개편 가시화 및 육해공 우주를 아우르는 방산 빅스텝 본격화."
        ),
        "causal_chain": (
            "글로벌 안보 위협 상시화 → 국내 방산 업계의 M&A 및 수직 계열화를 통한 글로벌 경쟁력 강화 "
            "→ 한화의 KAI 지분 15% 이상 확보로 육·해·공 우주 통합 솔루션 구축 → 방산 밸류체인 재평가 및 수주 경쟁력 제고."
        ),
        "total_score": 90,
        "directness": 23,
        "leverage": 22,
        "scalability_or_rotation": 23,
        "technical_alignment": 22,
        "directness_reason": "한화그룹의 KAI 지분 공시 15% 달성으로 실질적 거버넌스 변화 이벤트 발생.",
        "leverage_reason": "육해공 무기 체계와 우주항공 기술 결합을 통한 패키지 수출 협상력 및 락인 효과 극대화.",
        "scalability_or_rotation_reason": "지정학적 리스크(유가 상승, 중동 긴장) 장기화와 맞물려 방위산업 모멘텀 지속.",
        "technical_alignment_reason": "지분 매입 이벤트에 따른 수급 유입 및 방산주 섹터 순환매.",
        "market_timing": "공정위 기업결합심사 등 후속 절차 및 방산 연말 수주 랠리 (0-3개월).",
        "critical_risk": "기업결합심사 지연 또는 지정학적 긴장 조기 완화.",
        "raw_json": {
            "evidence_score": 19,
            "surprise_level": "Medium",
            "root_driver": "Geopolitical Tension & K-Defense M&A Consolidation",
            "transmission_confidence": "High",
            "bottleneck_rank": ["Aerospace & Defense M&A", "Global Defense Supply Chain"]
        },
        "candidates": [
            {"ticker": "272210", "name": "한화시스템", "role": "KAI 지분 매입 주체이자 우주항공·방산 전자 핵심 수혜주", "near_52w_high": 89.0, "ret_1m": 8.0, "ret_3m": 15.0, "early_signal_score": 89.0, "signal_flag": "🔺임박"},
            {"ticker": "047810", "name": "한국항공우주", "role": "한화그룹의 지분 매입 대상 및 육해공 거버넌스 재편 중심", "near_52w_high": 85.0, "ret_1m": 6.0, "ret_3m": 10.0, "early_signal_score": 88.0, "signal_flag": "📌중기후보"}
        ],
        "created_at": now_str
    }
]
'''

new_content = re.sub(r'ideas\s*=\s*\[.*\]\n', new_ideas_code, content, flags=re.DOTALL)
with open(file_path, 'w', encoding='utf-8') as f:
    f.write(new_content)
print('Successfully updated insert_today_ideas_v5.py')
