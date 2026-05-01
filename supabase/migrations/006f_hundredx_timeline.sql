-- 006f: 라이브러리 종목의 trigger timeline
-- 100배 종목은 한 번에 100배 오르지 않음. 보통 다음과 같은 시퀀스:
--   T-12mo: 지정학적/정책 변화 (배경 신호)
--   T-9mo:  첫 수주/MOU 공시 (초기 트리거 ★)
--   T-3mo:  메가계약 체결 (가속 트리거)
--   T0:     주가 상승 시작
--   T+3mo:  BCR 급등 / 재무 반영
--   T+6mo:  수주잔고 YoY 도약
--   T+9mo:  OPM 전환점
--   T+12mo: 매출 가속화
--
-- 각 트리거는 자체 fingerprint를 가짐 (해당 시점에 관측되는 신호).
-- 현재 종목은 이 timeline의 "어느 단계"에 도달했는지 측정 → 트리거 발화 횟수
-- 와 마지막 발화 후 경과 개월수로 100배 도달 가능성 추적.

-- triggers JSONB array 스키마:
-- [
--   {
--     "seq": 0,                       -- 시퀀스 인덱스 (0=가장 이른 단계)
--     "name": "지정학적_배경",         -- 트리거 이름 (사용자 가독)
--     "months_from_rise": -12,         -- rise_start_date 기준 (음수=이전, 양수=이후)
--     "signals": {                    -- 이 트리거가 발화하기 위한 신호 패턴
--       "quant": {"bcr_at_signal": 1.0},
--       "keywords": ["NATO","재무장","방산예산"],
--       "min_keyword_matches": 2
--     },
--     "weight": 1.0                   -- 이 트리거 매칭이 전체 score에 기여하는 가중치
--   },
--   ...
-- ]

ALTER TABLE hundredx_library_stocks
  ADD COLUMN IF NOT EXISTS triggers JSONB DEFAULT '[]'::jsonb;

COMMENT ON COLUMN hundredx_library_stocks.triggers IS
  'Trigger timeline: 시퀀스별 트리거 (rise_start 기준 ±N개월). 각 트리거는 발화 시점과 신호 패턴 포함.';

-- 매칭 결과를 저장할 컬럼 추가 (hundredx_category_matches)
-- timeline_progress JSONB:
-- {
--   "library_ticker": "012450",
--   "library_category": "수주잔고_선행",
--   "fired_triggers": [
--     {"seq": 0, "name": "지정학적_배경", "months_from_rise": -12, "fired_at_months_ago": 8},
--     {"seq": 1, "name": "최초_수주공시", "months_from_rise": -9, "fired_at_months_ago": 5}
--   ],
--   "current_position_months": -7,    -- 현재 종목이 라이브러리 timeline의 어느 시점에 해당
--   "trajectory_score": 0.4,           -- 발화 트리거 가중치 합 / 전체 가중치 합
--   "next_expected_trigger": {"seq": 2, "name": "메가계약_체결", "expected_in_months": 4}
-- }
ALTER TABLE hundredx_category_matches
  ADD COLUMN IF NOT EXISTS timeline_progress JSONB;

COMMENT ON COLUMN hundredx_category_matches.timeline_progress IS
  '라이브러리 timeline 매칭 진행도: 발화 트리거 / 위치 / 다음 예상 트리거';

-- ── 한화에어로 (012450) — 수주잔고_선행 timeline ─────────────────────────
-- rise_start = 2022-07-01, peak 20x
-- 실제 사건: 2021 NATO 재무장 → 2021 K-9 폴란드 사전협상 → 2022.02 우크라 침공 →
--             2022.07 K-9 9조원 계약 → 2022.10 BCR 2.8x → 2023.04 OPM 4%
UPDATE hundredx_library_stocks SET triggers = '[
  {
    "seq": 0,
    "name": "지정학적_배경 (T-12)",
    "months_from_rise": -12,
    "signals": {
      "keywords": ["NATO", "재무장", "방산예산", "리쇼어링", "에너지 안보"],
      "min_keyword_matches": 1,
      "sector_required": "방산"
    },
    "weight": 0.5
  },
  {
    "seq": 1,
    "name": "초기_수주공시 (T-9) ★",
    "months_from_rise": -9,
    "signals": {
      "keywords": ["수출", "수주", "방산", "K-9", "K-2", "폴란드"],
      "min_keyword_matches": 2,
      "sector_required": "방산"
    },
    "weight": 1.0
  },
  {
    "seq": 2,
    "name": "메가계약_체결 (T-3)",
    "months_from_rise": -3,
    "signals": {
      "keywords": ["폴란드", "K-9", "K-2", "FA-50", "조원", "수출"],
      "min_keyword_matches": 3,
      "amount_threshold_billions": 9000,
      "sector_required": "방산"
    },
    "weight": 1.5
  },
  {
    "seq": 3,
    "name": "BCR_급등 (T+3)",
    "months_from_rise": 3,
    "signals": {
      "quant": {"bcr_at_signal": 2.0}
    },
    "weight": 1.5
  },
  {
    "seq": 4,
    "name": "수주잔고_YoY_도약 (T+6)",
    "months_from_rise": 6,
    "signals": {
      "quant": {"backlog_yoy_pct": 100}
    },
    "weight": 1.0
  },
  {
    "seq": 5,
    "name": "OPM_전환 (T+9)",
    "months_from_rise": 9,
    "signals": {
      "quant": {"opm_at_signal": 4.0, "opm_prev": 2.0}
    },
    "weight": 1.0
  }
]'::jsonb WHERE ticker = '012450' AND category = '수주잔고_선행';

-- ── HD현대일렉 (267260) — 수주잔고_선행 timeline ────────────────────────
-- rise_start = 2023-01-01, peak 8.2x (real ~80x in 4y)
-- 2022.06 IRA 통과 → 2022.09 변압기 리드타임 36개월 → 2022.12 미국 유틸리티 수주 → 2023.04 BCR 1.4x
UPDATE hundredx_library_stocks SET triggers = '[
  {
    "seq": 0,
    "name": "정책_트리거 (T-9)",
    "months_from_rise": -9,
    "signals": {
      "keywords": ["IRA", "리쇼어링", "미국", "전력망", "에너지 안보"],
      "min_keyword_matches": 2,
      "sector_required": "전력기기"
    },
    "weight": 0.5
  },
  {
    "seq": 1,
    "name": "공급병목_뉴스 (T-6) ★",
    "months_from_rise": -6,
    "signals": {
      "keywords": ["변압기", "공급 부족", "리드타임", "납기", "미국"],
      "min_keyword_matches": 2,
      "sector_required": "전력기기"
    },
    "weight": 1.0
  },
  {
    "seq": 2,
    "name": "미국_수주공시 (T-3)",
    "months_from_rise": -3,
    "signals": {
      "keywords": ["HVDC", "변압기", "미국", "수주", "GIS"],
      "min_keyword_matches": 3,
      "sector_required": "전력기기"
    },
    "weight": 1.5
  },
  {
    "seq": 3,
    "name": "BCR_도약 (T+3)",
    "months_from_rise": 3,
    "signals": {"quant": {"bcr_at_signal": 1.4, "backlog_yoy_pct": 80}},
    "weight": 1.5
  },
  {
    "seq": 4,
    "name": "OPM_급반등 (T+6)",
    "months_from_rise": 6,
    "signals": {"quant": {"opm_at_signal": 5.0, "opm_prev": 1.5}},
    "weight": 1.0
  }
]'::jsonb WHERE ticker = '267260' AND category = '수주잔고_선행';

-- ── 효성중공업 (298040) — 수주잔고_선행 timeline ────────────────────────
UPDATE hundredx_library_stocks SET triggers = '[
  {
    "seq": 0,
    "name": "정책_트리거 (T-6)",
    "months_from_rise": -6,
    "signals": {
      "keywords": ["IRA", "전력망", "미국", "에너지 안보"],
      "min_keyword_matches": 1,
      "sector_required": "전력기기"
    },
    "weight": 0.5
  },
  {
    "seq": 1,
    "name": "수출_확대공시 (T-3) ★",
    "months_from_rise": -3,
    "signals": {
      "keywords": ["HVDC", "GIS", "변압기", "수출", "미국"],
      "min_keyword_matches": 2,
      "sector_required": "전력기기"
    },
    "weight": 1.0
  },
  {
    "seq": 2,
    "name": "BCR_전환점 (T+3)",
    "months_from_rise": 3,
    "signals": {"quant": {"bcr_at_signal": 1.0, "backlog_yoy_pct": 50}},
    "weight": 1.0
  },
  {
    "seq": 3,
    "name": "OPM_급반등 (T+6)",
    "months_from_rise": 6,
    "signals": {"quant": {"opm_at_signal": 8.0, "opm_prev": 2.0}},
    "weight": 1.5
  }
]'::jsonb WHERE ticker = '298040' AND category IN ('수주잔고_선행', '수익성_급전환');

-- ── 에코프로 (086520) — 공급_병목 timeline ───────────────────────────────
UPDATE hundredx_library_stocks SET triggers = '[
  {
    "seq": 0,
    "name": "EV_정책_배경 (T-12)",
    "months_from_rise": -12,
    "signals": {
      "keywords": ["EV", "전기차", "배터리", "공급망"],
      "min_keyword_matches": 1
    },
    "weight": 0.5
  },
  {
    "seq": 1,
    "name": "양극재_수요폭발 (T-6) ★",
    "months_from_rise": -6,
    "signals": {
      "keywords": ["양극재", "EV 배터리", "공급 부족", "수요"],
      "min_keyword_matches": 2
    },
    "weight": 1.0
  },
  {
    "seq": 2,
    "name": "CAPEX_증설 (T-3)",
    "months_from_rise": -3,
    "signals": {
      "keywords": ["증설", "신공장", "CAPEX", "양극재", "생산능력"],
      "min_keyword_matches": 2
    },
    "weight": 1.5
  },
  {
    "seq": 3,
    "name": "IRA_보조금 (T+3)",
    "months_from_rise": 3,
    "signals": {
      "keywords": ["IRA", "보조금", "리쇼어링", "북미", "공급망"],
      "min_keyword_matches": 2
    },
    "weight": 1.0
  },
  {
    "seq": 4,
    "name": "매출_급증 (T+6)",
    "months_from_rise": 6,
    "signals": {"quant": {"revenue_growth_yoy": 50}},
    "weight": 1.0
  }
]'::jsonb WHERE ticker = '086520' AND category = '공급_병목';

-- ── 알테오젠 (196170) — 임상_파이프라인 timeline ─────────────────────────
UPDATE hundredx_library_stocks SET triggers = '[
  {
    "seq": 0,
    "name": "FDA_IND_획득 (T-9)",
    "months_from_rise": -9,
    "signals": {
      "keywords": ["FDA IND", "임상", "Hybrozyme", "히알루로니다제"],
      "min_keyword_matches": 1,
      "sector_required": "바이오"
    },
    "weight": 1.0
  },
  {
    "seq": 1,
    "name": "기술이전_계약 (T-3) ★",
    "months_from_rise": -3,
    "signals": {
      "keywords": ["기술이전", "license out", "빅파마", "마일스톤", "SC 플랫폼"],
      "min_keyword_matches": 2,
      "amount_threshold_billions": 1000,
      "sector_required": "바이오"
    },
    "weight": 1.5
  },
  {
    "seq": 2,
    "name": "추가_파트너십 (T+3)",
    "months_from_rise": 3,
    "signals": {
      "keywords": ["기술이전", "빅파마", "마일스톤"],
      "min_keyword_matches": 1,
      "sector_required": "바이오"
    },
    "weight": 1.0
  },
  {
    "seq": 3,
    "name": "임상_진전 (T+6)",
    "months_from_rise": 6,
    "signals": {
      "keywords": ["임상", "Phase", "1상", "2상", "3상"],
      "min_keyword_matches": 1,
      "sector_required": "바이오"
    },
    "weight": 1.0
  }
]'::jsonb WHERE ticker = '196170' AND category = '임상_파이프라인';

-- ── 펩트론 (087010) — 임상_파이프라인 timeline ───────────────────────────
UPDATE hundredx_library_stocks SET triggers = '[
  {
    "seq": 0,
    "name": "FDA_IND_제출 (T-9)",
    "months_from_rise": -9,
    "signals": {"keywords": ["FDA IND", "임상시험계획", "GLP-1"], "min_keyword_matches": 1, "sector_required": "바이오"},
    "weight": 1.0
  },
  {
    "seq": 1,
    "name": "CDMO_파트너 (T-3) ★",
    "months_from_rise": -3,
    "signals": {"keywords": ["LG화학", "CDMO", "공급 계약", "유통"], "min_keyword_matches": 2, "sector_required": "바이오"},
    "weight": 1.5
  },
  {
    "seq": 2,
    "name": "신공장_증설 (T0)",
    "months_from_rise": 0,
    "signals": {"keywords": ["신공장", "CAPEX", "증설", "생산능력"], "min_keyword_matches": 2},
    "weight": 1.0
  },
  {
    "seq": 3,
    "name": "임상_단계_진전 (T+3)",
    "months_from_rise": 3,
    "signals": {"keywords": ["임상", "1상", "2상", "Phase"], "min_keyword_matches": 1},
    "weight": 1.0
  }
]'::jsonb WHERE ticker = '087010' AND category = '임상_파이프라인';

-- ── 우리기술 (032820) — 정책_수혜 timeline ───────────────────────────────
UPDATE hundredx_library_stocks SET triggers = '[
  {
    "seq": 0,
    "name": "정책_전환 (T-9)",
    "months_from_rise": -9,
    "signals": {
      "keywords": ["원전", "탈원전", "정책 전환", "에너지 안보"],
      "min_keyword_matches": 1,
      "sector_required": "원전"
    },
    "weight": 0.5
  },
  {
    "seq": 1,
    "name": "원안위_인증 (T-6) ★",
    "months_from_rise": -6,
    "signals": {
      "keywords": ["원안위", "MMIS", "인증", "갱신"],
      "min_keyword_matches": 1,
      "sector_required": "원전"
    },
    "weight": 1.0
  },
  {
    "seq": 2,
    "name": "체코_원전_입찰 (T0)",
    "months_from_rise": 0,
    "signals": {
      "keywords": ["체코", "두코바니", "원전", "입찰", "수주"],
      "min_keyword_matches": 2,
      "sector_required": "원전"
    },
    "weight": 1.5
  },
  {
    "seq": 3,
    "name": "BCR_급등 (T+3)",
    "months_from_rise": 3,
    "signals": {"quant": {"bcr_at_signal": 2.0, "backlog_yoy_pct": 50}},
    "weight": 1.0
  }
]'::jsonb WHERE ticker = '032820' AND category IN ('정책_수혜', '수주잔고_선행');

-- ── 한미반도체 (042700) — 플랫폼_독점 + 빅테크_파트너 timeline ──────────
UPDATE hundredx_library_stocks SET triggers = '[
  {
    "seq": 0,
    "name": "HBM_시장_확대 (T-9)",
    "months_from_rise": -9,
    "signals": {"keywords": ["HBM", "AI", "메모리"], "min_keyword_matches": 1, "sector_required": "반도체장비"},
    "weight": 0.5
  },
  {
    "seq": 1,
    "name": "TC본더_수주 (T-3) ★",
    "months_from_rise": -3,
    "signals": {"keywords": ["TC본더", "HBM", "SK하이닉스", "수주"], "min_keyword_matches": 2, "sector_required": "반도체장비"},
    "weight": 1.5
  },
  {
    "seq": 2,
    "name": "NVIDIA_파트너십 (T0)",
    "months_from_rise": 0,
    "signals": {"keywords": ["NVIDIA", "HBM", "공급 계약"], "min_keyword_matches": 2, "sector_required": "반도체장비"},
    "weight": 1.5
  },
  {
    "seq": 3,
    "name": "양산_확대 (T+3)",
    "months_from_rise": 3,
    "signals": {"keywords": ["양산", "수율", "증설"], "min_keyword_matches": 1},
    "weight": 1.0
  }
]'::jsonb WHERE ticker = '042700' AND category IN ('플랫폼_독점', '빅테크_파트너');

-- ── 레인보우로보틱스 (277810) — 빅테크_파트너 timeline (콜옵션 패턴) ──
UPDATE hundredx_library_stocks SET triggers = '[
  {
    "seq": 0,
    "name": "삼성_지분취득 (T0) ★",
    "months_from_rise": 0,
    "signals": {
      "keywords": ["삼성전자", "유상증자 참여", "전략적 투자", "지분 취득"],
      "min_keyword_matches": 2,
      "sector_required": "로봇"
    },
    "weight": 1.5
  },
  {
    "seq": 1,
    "name": "콜옵션_조항 (T0)",
    "months_from_rise": 0,
    "signals": {
      "keywords": ["콜옵션", "call option", "최대주주", "전환"],
      "min_keyword_matches": 1
    },
    "weight": 1.5
  },
  {
    "seq": 2,
    "name": "휴머노이드_관심 (T+3)",
    "months_from_rise": 3,
    "signals": {"keywords": ["휴머노이드", "humanoid", "협동로봇"], "min_keyword_matches": 1},
    "weight": 1.0
  }
]'::jsonb WHERE ticker = '277810' AND category = '빅테크_파트너';

-- ── 로보티즈 (108490) ────────────────────────────────────────────────────
UPDATE hundredx_library_stocks SET triggers = '[
  {
    "seq": 0,
    "name": "LG_지분투자 (T-9) ★",
    "months_from_rise": -9,
    "signals": {
      "keywords": ["LG전자", "지분 취득", "전략적 투자", "유상증자"],
      "min_keyword_matches": 2,
      "amount_threshold_billions": 90,
      "sector_required": "로봇"
    },
    "weight": 1.5
  },
  {
    "seq": 1,
    "name": "휴머노이드_채택 (T-3)",
    "months_from_rise": -3,
    "signals": {
      "keywords": ["Dynamixel", "휴머노이드", "humanoid", "오픈AI", "구글"],
      "min_keyword_matches": 1
    },
    "weight": 1.0
  },
  {
    "seq": 2,
    "name": "학술_채택 (T+3)",
    "months_from_rise": 3,
    "signals": {"keywords": ["Dynamixel", "액추에이터", "학술", "논문"], "min_keyword_matches": 1},
    "weight": 1.0
  }
]'::jsonb WHERE ticker = '108490' AND category IN ('플랫폼_독점', '빅테크_파트너');

-- ── 대한광통신 (010170) ──────────────────────────────────────────────────
UPDATE hundredx_library_stocks SET triggers = '[
  {
    "seq": 0,
    "name": "수직계열화_완성 (T-12)",
    "months_from_rise": -12,
    "signals": {"keywords": ["광섬유", "광케이블", "모재", "수직계열화"], "min_keyword_matches": 2, "sector_required": "광통신"},
    "weight": 1.0
  },
  {
    "seq": 1,
    "name": "AI_DC_수요폭발 (T-3) ★",
    "months_from_rise": -3,
    "signals": {"keywords": ["AI 데이터센터", "광섬유", "수요", "빅테크"], "min_keyword_matches": 2, "sector_required": "광통신"},
    "weight": 1.5
  },
  {
    "seq": 2,
    "name": "공급_부족_확인 (T+3)",
    "months_from_rise": 3,
    "signals": {"keywords": ["공급 부족", "수급 불균형", "납기"], "min_keyword_matches": 1},
    "weight": 1.0
  }
]'::jsonb WHERE ticker = '010170' AND category IN ('플랫폼_독점', '공급_병목');

-- ── 삼천당제약 (000250) ──────────────────────────────────────────────────
UPDATE hundredx_library_stocks SET triggers = '[
  {
    "seq": 0,
    "name": "GLP-1_플랫폼_확보 (T-12)",
    "months_from_rise": -12,
    "signals": {"keywords": ["GLP-1", "S-PASS", "경구형", "세마글루타이드"], "min_keyword_matches": 1, "sector_required": "바이오"},
    "weight": 0.5
  },
  {
    "seq": 1,
    "name": "일본_기술이전 (T-9)",
    "months_from_rise": -9,
    "signals": {"keywords": ["일본", "기술이전", "license out", "마일스톤"], "min_keyword_matches": 2, "sector_required": "바이오"},
    "weight": 1.0
  },
  {
    "seq": 2,
    "name": "유럽_라이선스 (T-3) ★",
    "months_from_rise": -3,
    "signals": {"keywords": ["유럽", "라이선스", "기술이전"], "min_keyword_matches": 2, "amount_threshold_billions": 5000, "sector_required": "바이오"},
    "weight": 1.5
  },
  {
    "seq": 3,
    "name": "미국_본계약 (T+3)",
    "months_from_rise": 3,
    "signals": {"keywords": ["미국", "FDA", "기술이전", "본계약"], "min_keyword_matches": 1},
    "weight": 1.0
  }
]'::jsonb WHERE ticker = '000250' AND category = '임상_파이프라인';
