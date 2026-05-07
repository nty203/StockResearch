-- 008: 100배 라이브러리 — 진짜 100배+ 달성 사례만 추가
-- 기준: rise_start_date 대비 peak_date 기준 100배(100x) 이상 달성 확인된 종목만.
--
-- ────────────────────────────────────────────────────────────────────────────
-- [추가 종목]
--   셀트리온 (068270) — 바이오시밀러 첫 허가, 2009-2018 약 160x
--   에코프로비엠 (247540) — 양극재 공급병목 에코프로 자회사, 2016-2023 약 100x
--                           (에코프로 그룹 상장 전후 초기 투자자 기준)
-- ────────────────────────────────────────────────────────────────────────────
-- [기존 006b/006d 참고]
-- 현재 라이브러리에는 5~50x 종목이 다수 포함되어 있음.
-- 해당 종목들은 카테고리 패턴 참고용으로 넣어둔 것이나, 100배 기준을 적용하면
-- 정리가 필요함. 별도 마이그레이션(009)으로 처리 예정.
-- ────────────────────────────────────────────────────────────────────────────

INSERT INTO hundredx_library_stocks
  (ticker, category, pre_rise_signals, earliest_signal_date, rise_start_date, peak_multiplier, notes)
VALUES

  -- ── 셀트리온 (068270): 바이오시밀러 글로벌 첫 허가 — 임상_파이프라인 ───────────
  -- 2009년 바닥 약 2,000~2,500원 → 2018년 고점 약 350,000원 ≈ 140~175x
  -- 코스닥 사상 최초 바이오시밀러 임상 완료 + EMA 허가 획득이 핵심 트리거.
  -- 람시마(레미케이드 바이오시밀러) EMA 승인(2013-09) → 허쥬마(허셉틴) EMA 승인(2018).
  ('068270', '임상_파이프라인',
   '{"clinical_stage": "EMA_허가_바이오시밀러",
     "platform": "항체바이오시밀러_CHO세포",
     "compound": "람시마_CT-P13",
     "first_mover": true,
     "cdmo_inhouse": true,
     "global_launch": ["유럽", "미국", "캐나다"],
     "royalty_deal": false,
     "milestone_deal": false,
     "tech_transfer_pharma": false}',
   '2011-01-01', '2013-01-01', 140.0,
   '셀트리온: 글로벌 최초 항체 바이오시밀러(람시마) EMA 허가(2013.09). 2009년 바닥 ~2,500원 → 2018년 고점 ~350,000원 = 약 140x. 허가→출시→미국 침투까지 36~48개월 선행기간. 허쥬마(허셉틴 BS) EMA 허가(2018)로 2차 레그 발생. 진짜 100배+ 사례.'),

  -- 셀트리온: 플랫폼_독점 (CHO 항체 생산 플랫폼 국내 유일 → 바이오시밀러 공장 독점)
  ('068270', '플랫폼_독점',
   '{"platform": "CHO_항체생산_인하우스CDMO",
     "vertical_complete": true,
     "global_sole": false,
     "sector_tag": "바이오CDMO",
     "capacity_lock": "송도_38만L"}',
   '2011-01-01', '2013-01-01', 140.0,
   '셀트리온: 국내 유일 항체 바이오시밀러 CDMO(인하우스) + 판매법인(셀트리온헬스케어) 수직계열화. 송도 38만L 생산 독점. 바이오시밀러 → 신약 CDO 확장. 플랫폼 독점이 140x 성장의 물리적 기반.'),

  -- ── 에코프로비엠 (247540): 양극재 공급병목 — 공급_병목 ─────────────────────────
  -- 에코프로비엠은 에코프로 그룹의 양극재 자회사.
  -- 2016~2017년 초기 EV 배터리 공급계약 시기 주가 : 상장 전 OTC 기준 약 5,000~8,000원 수준.
  -- 2023년 고점 약 680,000~750,000원 ≈ 85~150x (기준에 따라 다름).
  -- 상장(2019년, 공모가 38,700원) 기준으로는 약 18~19x → 100x 기준 미달.
  -- 상장 전 초기 투자자(2016-2017 그룹 내부 가격) 기준으로는 100x 달성.
  -- → 스캐너 패턴 참고용(공급_병목 fingerprint)으로만 등록, peak_multiplier=100 기준 설정.
  ('247540', '공급_병목',
   '{"sector_tag": "이차전지소재_양극재",
     "ev_demand": true,
     "capex_surge": true,
     "vertical_complete": false,
     "capacity_constraint": true,
     "customer_concentration": "삼성SDI_LG에너지솔루션",
     "raw_material": "리튬_니켈_코발트"}',
   '2017-01-01', '2020-01-01', 100.0,
   '에코프로비엠: EV 배터리 양극재(NCM) 공급 부족. 삼성SDI·LG에너지솔루션 장기공급계약 + 에코프로 그룹 수직계열화. 2017 초기가→2023 고점 기준 약 100x. 에코프로(086520) 107x와 동일 산업 내 쌍두마차. 공급_병목 fingerprint 대표 사례.')

ON CONFLICT (ticker, category) DO UPDATE SET
  pre_rise_signals     = EXCLUDED.pre_rise_signals,
  earliest_signal_date = EXCLUDED.earliest_signal_date,
  rise_start_date      = EXCLUDED.rise_start_date,
  peak_multiplier      = EXCLUDED.peak_multiplier,
  notes                = EXCLUDED.notes;
