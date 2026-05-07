-- 014: 역대 100배 종목 추가 (한미반도체, 신풍제약, 셀트리온, 알테오젠)
--
-- ─────────────────────────────────────────────────────────────────────────────

INSERT INTO hundredx_library_stocks
  (ticker, category, pre_rise_signals, earliest_signal_date, rise_start_date, peak_multiplier, notes)
VALUES

  -- ── 한미반도체 (042700): AI HBM TC 본더 독점 ──────────────────────────────────
  ('042700', '공급_병목',
   '{"sector_tag": "반도체장비_HBM",
     "product": ["TC_Bonder"],
     "ai_gpu_correlation": "hynix_nvidia_hbm",
     "monopoly": true,
     "pricing_power": true}',
   '2023-01-01', '2022-09-30', 15.0,
   '한미반도체: HBM 제조 필수 장비인 TC 본더 글로벌 독점 공급. AI 반도체 붐의 직접 수혜. 15배 이상 상승 중이며 장기 100배 가능성 높음.'),

  -- ── 신풍제약 (019170): COVID-19 치료제 기대감 ───────────────────────────────
  ('019170', '정책_수혜',
   '{"sector_tag": "제약바이오_팬데믹",
     "product": ["피라마맥스"],
     "catalyst": "COVID19_clinical_trial",
     "volatility": "extreme"}',
   '2020-02-01', '2020-01-20', 35.0,
   '신풍제약: 코로나19 치료제(피라마맥스) 임상 기대감으로 급등. 단기 35배 이상 상승 후 하락. 전형적인 뉴스/임상 기반 폭등 사례.'),

  -- ── 셀트리온 (068270): 바이오시밀러 개척자 ──────────────────────────────────
  ('068270', '산업_혁신',
   '{"sector_tag": "바이오시밀러",
     "product": ["램시마", "트룩시마"],
     "global_first": true,
     "fda_approval": true}',
   '2008-01-01', '2008-10-27', 80.0,
   '셀트리온: 바이오시밀러 시장 개척 및 글로벌 진출 성공. 10년 이상의 장기 성장을 통해 80배 이상 상승.'),

  -- ── 알테오젠 (196170): SC 제형 변경 플랫폼 ──────────────────────────────────
  ('196170', '기술_독점',
   '{"sector_tag": "바이오플랫폼",
     "product": ["ALT-B4"],
     "licensing_deal": ["Merck", "Sandoz"],
     "platform_scaling": true}',
   '2019-01-01', '2019-01-02', 45.0,
   '알테오젠: 정맥주사를 피하주사로 바꾸는 SC 제형 변경 플랫폼 기술 보유. 글로벌 빅테크(머크 등)와의 대규모 라이선스 딜로 가치 재평가.')

ON CONFLICT (ticker, category) DO UPDATE SET
  pre_rise_signals     = EXCLUDED.pre_rise_signals,
  earliest_signal_date = EXCLUDED.earliest_signal_date,
  rise_start_date      = EXCLUDED.rise_start_date,
  peak_multiplier      = EXCLUDED.peak_multiplier,
  notes                = EXCLUDED.notes;
