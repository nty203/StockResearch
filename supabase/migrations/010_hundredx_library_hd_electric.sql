-- 010: 100배 라이브러리 — HD현대일렉트릭 (267260) 추가
--
-- 배경:
--   2020 COVID 저점(4,900원) → 2026-05 현재(1,389,000원) = 283.5x 달성.
--   2025-06-25 기준으로 처음 100x(497,000원) 돌파 (저점 대비 5년 3개월).
--   AI 데이터센터 전력 인프라 수요 급증 + 글로벌 변압기 공급 부족이 핵심 트리거.
--   수주잔고가 주가보다 먼저 폭증 (2023 수주잔고_선행 시그널 발현).
--
-- [주가 경로]
--   COVID 저점: 2020-03-19, 4,900원
--   AI 테마 이전 2023 Q1: ~39,000원 (저점 대비 8x, 실질 상승 전 단계)
--   100x 돌파: 2025-06-25, 497,000원
--   현재 최고점: 2026-05-06, 1,389,000원 (283.5x)
--
-- 카테고리:
--   수주잔고_선행: 2023년 글로벌 수주 폭증이 실적 개선보다 2~3분기 선행
--   공급_병목: 대형 변압기 납기 2~3년, 글로벌 생산능력 부족
-- ─────────────────────────────────────────────────────────────────────────────

INSERT INTO hundredx_library_stocks
  (ticker, category, pre_rise_signals, earliest_signal_date, rise_start_date, peak_multiplier, notes)
VALUES

  -- ── HD현대일렉트릭 (267260): 수주잔고_선행 ────────────────────────────────────
  -- 2023년 초 AI 데이터센터 전력 수요 확인 → 수주잔고 급증 공시 선행
  -- 2023 Q2~Q3 수주잔고 조 단위 돌파 → 주가 수직 상승 시작
  ('267260', '수주잔고_선행',
   '{"sector_tag": "전력기기_변압기_개폐기",
     "order_backlog_surge": true,
     "global_market": ["미국", "중동", "유럽"],
     "customer_type": "전력유틸리티_데이터센터",
     "lead_time_years": 2.5,
     "domestic_monopoly": true,
     "vertically_integrated": true,
     "catalyst": "AI_데이터센터_전력인프라",
     "ira_beneficiary": true}',
   '2023-01-01', '2020-03-19', 283.5,
   'HD현대일렉트릭: AI 데이터센터 전력 인프라 + 글로벌 변압기 수급난. COVID 저점 2020-03-19(4,900원) → 2026-05(1,389,000원) = 283.5x. 2025-06-25 처음 100x(497,000원) 돌파. 2023년 수주잔고 조 단위 공시 → 납기 2~3년 수주 선행 시그널 발현. 국내 중고압 전력기기 시장 지배적 사업자. 수주잔고_선행 대표 사례.'),

  -- ── HD현대일렉트릭 (267260): 공급_병목 ───────────────────────────────────────
  -- 글로벌 대형 변압기 공급부족: 제조 리드타임 2~3년, 신규 설비투자 미비
  -- AI 인프라 전력수요 폭발 + 에너지전환(재생에너지 연계 변압기) 겹침
  ('267260', '공급_병목',
   '{"sector_tag": "대형변압기_전력기기",
     "capacity_constraint": true,
     "global_shortage": true,
     "lead_time": "24~36개월",
     "demand_driver": ["AI데이터센터", "재생에너지", "노후그리드교체"],
     "supply_barrier": "신규공장_건설_최소3년",
     "pricing_power": true,
     "ira_beneficiary": true}',
   '2023-01-01', '2020-03-19', 283.5,
   'HD현대일렉트릭: 글로벌 대형 변압기 공급 부족. AI 데이터센터 전력 수요 + 재생에너지 연계 수요 동시 폭증. 대형 변압기 납기 24~36개월 → 가격 협상력 급상승. 2023~2026 수주 폭증 → 영업이익 수백% 성장. 공급_병목 패턴 대표 사례. 同 패턴: 에코프로(양극재), 반도체 장비 등.')

ON CONFLICT (ticker, category) DO UPDATE SET
  pre_rise_signals     = EXCLUDED.pre_rise_signals,
  earliest_signal_date = EXCLUDED.earliest_signal_date,
  rise_start_date      = EXCLUDED.rise_start_date,
  peak_multiplier      = EXCLUDED.peak_multiplier,
  notes                = EXCLUDED.notes;
