-- 012: 100배 라이브러리 카테고리화 — 자동 발견된 미분류 종목 정리
--
-- 대상 종목:
--   에코앤드림   (101360)  294x  공급_병목 (전구체)
--   코스모신소재 (005070)  109x  공급_병목 (양극재/MLCC)
--   제이엔케이히터 (107640) 107x  정책_수혜 (수소)
--   이수페타시스 (007660)  104x  공급_병목 (AI PCB)
-- ─────────────────────────────────────────────────────────────────────────────

INSERT INTO hundredx_library_stocks
  (ticker, category, pre_rise_signals, earliest_signal_date, rise_start_date, peak_multiplier, notes)
VALUES

  -- ── 에코앤드림 (101360): 294x — 이차전지 전구체 공급_병목 ──────────────────────
  -- 2018-12-17(227) → 2024-03-06(66,935) = 294x
  ('101360', '공급_병목',
   '{"sector_tag": "이차전지소재_전구체",
     "product": ["전구체", "촉매"],
     "capacity_constraint": true,
     "global_shortage": true,
     "demand_driver": ["EV배터리", "에코프로그룹_밸류체인"],
     "capex_surge": true,
     "pricing_power": true}',
   '2020-01-01', '2018-12-17', 294.9,
   '에코앤드림: 이차전지 전구체 공급 부족 수혜. 에코프로 그룹과 긴밀한 밸류체인 형성. 상장 전후 저점 대비 최대 294배 상승. 전구체 자급화 및 증설 시그널이 핵심.'),

  -- ── 코스모신소재 (005070): 109x — 이차전지 양극재 공급_병목 ──────────────────────
  -- 2016-06-27(2,125) → 2023-06-13(231,645) = 109x
  ('005070', '공급_병목',
   '{"sector_tag": "이차전지소재_양극재",
     "product": ["NCM양극재", "MLCC이형필름"],
     "capacity_constraint": true,
     "customer_type": ["삼성SDI", "LG에너지솔루션"],
     "vertical_complete": false,
     "lead_time": "12~24개월",
     "pricing_power": true}',
   '2018-01-01', '2016-06-27', 109.0,
   '코스모신소재: NCM 양극재 및 MLCC 필름 공급 부족. 2016년 저점 대비 100배 이상 성장. 삼성SDI 등 주요 고객사 대규모 증설 및 공급 계약이 주가 견인.'),

  -- ── 제이엔케이히터 (107640): 107x — 수소 충전 인프라 정책_수혜 ──────────────────
  -- 2017-09-27(676) → 2026-04-21(72,500) = 107x
  ('107640', '정책_수혜',
   '{"sector_tag": "수소에너지_산업용가열로",
     "policy_driver": ["수소경제로드맵", "수소충전소확대", "탄소중립"],
     "product": ["수소추출기", "충전소구축", "가열로"],
     "government_backed": true,
     "global_market": ["사우디", "중동", "동남아"],
     "first_mover": true}',
   '2019-01-01', '2017-09-27', 107.2,
   '제이엔케이히터: 정부 수소 로드맵 수혜 + 산업용 가열로 독보적 지위. 수소 충전소 인프라 구축의 핵심 기업으로 부각되며 100배 이상 상승.'),

  -- ── 이수페타시스 (007660): 104x — AI 가속기용 PCB 공급_병목 ──────────────────
  -- 2020-03-19(1,543) → 2026-04-22(161,400) = 104x
  ('007660', '공급_병목',
   '{"sector_tag": "반도체기판_MLB",
     "product": "고다층_PCB_MLB",
     "capacity_constraint": true,
     "ai_gpu_correlation": "nvidia_H100_H200",
     "customer_concentration": ["Google", "NVIDIA", "MSFT"],
     "lead_time": "6~12개월",
     "pricing_power": true}',
   '2022-01-01', '2020-03-19', 104.6,
   '이수페타시스: AI 서버용 MLB(고다층 기판) 공급 부족. Google, NVIDIA 등 빅테크향 매출 급증. COVID 저점 대비 100배 이상 상승. 데이터센터 증설에 따른 기판 병목 현상의 직접적 수혜.')

ON CONFLICT (ticker, category) DO UPDATE SET
  pre_rise_signals     = EXCLUDED.pre_rise_signals,
  earliest_signal_date = EXCLUDED.earliest_signal_date,
  rise_start_date      = EXCLUDED.rise_start_date,
  peak_multiplier      = EXCLUDED.peak_multiplier,
  notes                = EXCLUDED.notes;

-- 기존 '미분류' 행이 있으면 삭제 (위의 INSERT로 정식 카테고리가 생성되므로)
DELETE FROM hundredx_library_stocks
WHERE ticker IN ('101360', '005070', '107640', '007660')
  AND category = '미분류';
