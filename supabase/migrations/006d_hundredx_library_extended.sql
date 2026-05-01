-- 006d: 라이브러리 시드 확장 — /backtest 페이지의 12개 reference stocks와 동기화
-- 기존 9개 + 신규 3개 (에코프로/한미반도체/알테오젠) — 에코프로 107x로 진짜 100배+ 포함
--
-- 멀티-카테고리 종목은 같은 ticker로 여러 row 삽입 (예: 효성중공업 → 수주잔고_선행 + 수익성_급전환).
-- 카테고리 매칭 시 각 row가 독립적으로 analog 후보가 됨.
--
-- 기존 행은 ON CONFLICT DO UPDATE로 peak_multiplier만 동기화 (NULL이 아닐 때).
-- 멀티 카테고리 추가 row는 별개 ticker+category 조합이라 INSERT 됨.

-- 멀티 카테고리 매칭을 위해 (ticker, category) UNIQUE 제약이 필요
ALTER TABLE hundredx_library_stocks
  DROP CONSTRAINT IF EXISTS hundredx_library_stocks_ticker_category_key;
ALTER TABLE hundredx_library_stocks
  ADD CONSTRAINT hundredx_library_stocks_ticker_category_key UNIQUE (ticker, category);

INSERT INTO hundredx_library_stocks
  (ticker, category, pre_rise_signals, earliest_signal_date, rise_start_date, peak_multiplier, notes)
VALUES
  -- ── 에코프로: 진짜 100배+ 종목 ────────────────────────────────────────────
  ('086520', '공급_병목',
   '{"sector_tag": "양극재", "ev_demand": true, "capex_surge": true}',
   '2019-06-01', '2020-01-01', 107.0,
   '에코프로: EV 배터리 공급 부족 + 양극재 증설 + IRA 수혜. 실제 100배+ 사례.'),

  -- ── 한미반도체: TC본더 글로벌 유일 ───────────────────────────────────────
  ('042700', '플랫폼_독점',
   '{"sector_tag": "반도체장비", "global_sole": true, "product": "TC본더"}',
   '2020-06-01', '2021-01-01', 19.0,
   '한미반도체: TC본더 글로벌 유일 공급사 + NVIDIA HBM 라인 수주.'),
  ('042700', '빅테크_파트너',
   '{"bigtech": "NVIDIA", "product": "TC본더_HBM"}',
   '2020-06-01', '2021-01-01', 19.0,
   '한미반도체: NVIDIA HBM 생산 라인 수주 — 빅테크 CAPEX 연동.'),

  -- ── 알테오젠: SC 플랫폼 빅파마 기술이전 ──────────────────────────────────
  ('196170', '임상_파이프라인',
   '{"clinical_stage": "FDA_IND_획득", "platform": "Hybrozyme_SC", "tech_transfer_pharma": true}',
   '2019-06-01', '2020-01-01', 50.0,
   '알테오젠: SC 플랫폼(Hybrozyme) 글로벌 빅파마 기술이전 + FDA IND.'),

  -- ── 효성중공업: 수주잔고_선행 + 수익성_급전환 (멀티 카테고리) ────────────
  ('298040', '수익성_급전환',
   '{"opm_delta_at_signal": 6.0, "opm_prev": 2.0, "opm_now": 8.0}',
   '2022-01-01', '2022-10-01', 18.0,
   '효성중공업: OPM 2%→8% 급반등. 수주잔고와 수익성 동시 신호.'),

  -- ── 한화에어로: 수주잔고_선행 + 정책_수혜 (멀티 카테고리) ────────────────
  ('012450', '정책_수혜',
   '{"policy_event": "NATO_재무장", "sector_tag": "방산", "export": "폴란드_K9"}',
   '2021-09-01', '2022-07-01', 20.0,
   '한화에어로스페이스: NATO 재무장 + 폴란드 K-9 9조원 수출. 정책 + 수주 동시.'),

  -- ── HD현대일렉: 수주잔고_선행 + 정책_수혜 (멀티 카테고리) ────────────────
  ('267260', '정책_수혜',
   '{"policy_event": "IRA_미국전력망", "sector_tag": "전력기기", "export": "미국_변압기"}',
   '2022-04-01', '2023-01-01', 8.2,
   'HD현대일렉트릭: IRA 이후 미국 전력망 투자 2배. HVDC 변압기 수주.'),

  -- ── 로보티즈: 플랫폼_독점 + 빅테크_파트너 (멀티 카테고리) ────────────────
  ('108490', '빅테크_파트너',
   '{"bigtech": "LG전자", "stake_amount_won": 9000000000}',
   '2022-01-01', '2023-06-01', 12.0,
   '로보티즈: LG전자 90억 전략 지분투자. 휴머노이드 Dynamixel 채택과 결합.'),

  -- ── 대한광통신: 플랫폼_독점 + 공급_병목 (멀티 카테고리) ──────────────────
  ('010170', '플랫폼_독점',
   '{"vertical_complete": true, "platform": "광섬유_수직계열화_국내유일"}',
   '2023-01-01', '2024-01-01', 35.0,
   '대한광통신: 국내 유일 모재→광섬유→광케이블 수직계열화. AI DC 수요 폭발.'),

  -- ── 우리기술: 정책_수혜 + 수주잔고_선행 (멀티 카테고리) ──────────────────
  ('032820', '수주잔고_선행',
   '{"bcr_at_signal": 3.0, "backlog_yoy_pct": 80, "policy_event": "원전_재개"}',
   '2022-06-01', '2023-06-01', 13.0,
   '우리기술: 체코 두코바니 원전 입찰 + MMIS 수주잔고/매출 3배.')

ON CONFLICT (ticker, category) DO UPDATE SET
  pre_rise_signals     = EXCLUDED.pre_rise_signals,
  earliest_signal_date = EXCLUDED.earliest_signal_date,
  rise_start_date      = EXCLUDED.rise_start_date,
  peak_multiplier      = EXCLUDED.peak_multiplier,
  notes                = EXCLUDED.notes;

-- 기존 9개 row의 peak_multiplier 업데이트 (006b seed보다 정확한 값)
UPDATE hundredx_library_stocks SET peak_multiplier = 107.0, notes = '에코프로: EV 배터리 공급 부족 + 양극재 증설 + IRA 수혜.' WHERE ticker = '086520';
UPDATE hundredx_library_stocks SET peak_multiplier = 19.0   WHERE ticker = '042700' AND category = '플랫폼_독점';
UPDATE hundredx_library_stocks SET peak_multiplier = 50.0   WHERE ticker = '196170' AND category = '임상_파이프라인';
UPDATE hundredx_library_stocks SET peak_multiplier = 18.0   WHERE ticker = '298040' AND category = '수주잔고_선행';
UPDATE hundredx_library_stocks SET peak_multiplier = 20.0   WHERE ticker = '012450' AND category = '수주잔고_선행';
UPDATE hundredx_library_stocks SET peak_multiplier = 8.2    WHERE ticker = '267260' AND category = '수주잔고_선행';
UPDATE hundredx_library_stocks SET peak_multiplier = 12.0   WHERE ticker = '108490' AND category = '플랫폼_독점';
UPDATE hundredx_library_stocks SET peak_multiplier = 35.0   WHERE ticker = '010170' AND category = '공급_병목';
UPDATE hundredx_library_stocks SET peak_multiplier = 4.5    WHERE ticker = '000250' AND category = '임상_파이프라인';
UPDATE hundredx_library_stocks SET peak_multiplier = 20.0   WHERE ticker = '277810' AND category = '빅테크_파트너';
UPDATE hundredx_library_stocks SET peak_multiplier = 41.0   WHERE ticker = '087010' AND category = '임상_파이프라인';
UPDATE hundredx_library_stocks SET peak_multiplier = 13.0   WHERE ticker = '032820' AND category = '정책_수혜';
