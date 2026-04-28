-- Seed: 100x research library — 9 confirmed historical cases
-- Sources:
--   docs/case-study-100x-signal-analysis.md  (3 stocks: 수주잔고_선행)
--   docs/signal-expansion-plan.md            (6 stocks: platform adoption types)
--
-- pre_rise_signals JSONB: key numeric signals at the time the pattern first appeared
--   bcr_at_signal         → backlog_lead.py analog matching
--   opm_delta_at_signal   → profit_inflect.py analog matching
--   (text detector fields are metadata only, not used for quantitative matching)
--
-- Add more rows via /hundredx/library admin UI (TODO-03) or manual INSERT.

INSERT INTO hundredx_library_stocks
  (ticker, category, pre_rise_signals, earliest_signal_date, rise_start_date, peak_multiplier, notes)
VALUES

  -- ── 수주잔고_선행 (3 cases) ──────────────────────────────────────────────

  ('012450', '수주잔고_선행',
   '{"bcr_at_signal": 2.8, "backlog_yoy_pct": 115, "opm_at_signal": 2.8}',
   '2021-09-01', '2022-07-01', 20.0,
   '한화에어로스페이스: 폴란드 K-9/K-2/FA-50 수주. BCR 2.8x, 수주잔고 YoY +115%. 주가 약 9개월 선행.'),

  ('267260', '수주잔고_선행',
   '{"bcr_at_signal": 1.4, "backlog_yoy_pct": 100, "opm_at_signal": 3.0}',
   '2022-04-01', '2023-01-01', 8.2,
   'HD현대일렉트릭: 미국 변압기 리드타임 36개월. BCR 1.4x, 수주잔고 YoY +100%. 공급_병목과 교차 확인.'),

  ('298040', '수주잔고_선행',
   '{"bcr_at_signal": 1.0, "backlog_yoy_pct": 50, "opm_at_signal": 2.5}',
   '2022-01-01', '2022-10-01', 5.0,
   '효성중공업: HVDC·GIS 미국 전력망 수주. BCR 1.0x→1.5x. 중공업 mix 60% 전환점.'),

  -- ── 빅테크_파트너 (1 case) ────────────────────────────────────────────────

  ('277810', '빅테크_파트너',
   '{"bigtech": "삼성전자", "has_callopt": true, "stake_pct": 14.7}',
   '2023-01-01', '2023-01-26', 15.0,
   '레인보우로보틱스: 삼성전자 유상증자+콜옵션 공시 당일 급등. 콜옵션 = 지배구조 변화 예고. 선행기간 0일 (공시 즉시).'),

  -- ── 플랫폼_독점 (1 case) ─────────────────────────────────────────────────

  ('108490', '플랫폼_독점',
   '{"bigtech": "LG전자", "platform": "Dynamixel", "academic_adoption": true}',
   '2022-01-01', '2023-06-01', 10.0,
   '로보티즈: LG전자 전략적 지분투자 + Dynamixel 학술 논문 채택률 급증. 매출 발생 18~36개월 선행.'),

  -- ── 정책_수혜 (1 case) ───────────────────────────────────────────────────

  ('032820', '정책_수혜',
   '{"policy_event": "탈원전_철회", "sector_tag": "원전", "cert_renewed": true}',
   '2022-06-01', '2023-06-01', 8.0,
   '우리기술: 원안위 인증 갱신 + 탈원전→원전 정책 전환. MMIS 독점 지위 유지. 선행 12개월.'),

  -- ── 공급_병목 (1 case) ───────────────────────────────────────────────────

  ('010170', '공급_병목',
   '{"supply_event": "AI_DC_광섬유_부족", "vertical_complete": true}',
   '2023-01-01', '2024-01-01', 12.0,
   '대한광통신: 수직계열화 완성 + AI 데이터센터 광섬유 공급 부족. 선행 24개월.'),

  -- ── 임상_파이프라인 (2 cases) ────────────────────────────────────────────

  ('000250', '임상_파이프라인',
   '{"clinical_stage": "기술이전_3개국", "compound": "경구형_GLP-1", "royalty_deal": true}',
   '2022-01-01', '2024-01-01', 15.0,
   '삼천당제약: 경구형 GLP-1 일본→유럽→미국 기술이전 순차 계약. 선행 24개월. 오젬픽 대항마.'),

  ('087010', '임상_파이프라인',
   '{"clinical_stage": "FDA_IND_승인", "cdmo_partner": "LG화학", "new_factory": true}',
   '2022-06-01', '2023-06-01', 10.0,
   '펩트론: FDA IND 승인 + 신공장 건설 + LG화학 유통 계약 3중 시그널. 선행 18개월.')

ON CONFLICT DO NOTHING;
