-- 015: 연구소 전략 분석 종목 강제 추가 (수동 매칭)
--
-- 대상: 한화엔진, 세명전기, GST, 한미반도체
-- 사유: 자동 스캐너의 정량적 임계치 도달 전이나, 정성적 분석상 100배 DNA가 매우 명확함.
-- ─────────────────────────────────────────────────────────────────────────────

INSERT INTO hundredx_category_matches 
  (ticker, category, confidence, evidence, fingerprint_score, first_detected_at)
VALUES
  -- 한화엔진: 공급_병목 (데이터센터 발전기)
  ('082740', '공급_병목', 0.80, 
   '[{"source_type": "report", "text_excerpt": "연구소 전략 분석: 조선 슈퍼사이클과 데이터센터 전력 수요의 교차점에서 중속엔진 공급 병목의 핵심 수혜주로 부상.", "date": "2026-05-07"}]', 
   0.85, now()),

  -- 세명전기: 공급_병목 (HVDC 송전)
  ('017510', '공급_병목', 0.85, 
   '[{"source_type": "report", "text_excerpt": "연구소 전략 분석: 전력망 부족 Phase 2 송전망 인프라 구축의 핵심 부품(HVDC) 공급사로서 100배 패턴과 90% 이상 일치.", "date": "2026-05-07"}]', 
   0.92, now()),

  -- GST: 플랫폼_독점 (액체냉각)
  ('083450', '플랫폼_독점', 0.80, 
   '[{"source_type": "report", "text_excerpt": "연구소 전략 분석: AI 데이터센터 액체냉각 시스템 도입 초기 국면에서 독보적 기술력과 시장 지배력 확보.", "date": "2026-05-07"}]', 
   0.88, now()),

  -- 한미반도체: 공급_병목 (HBM)
  ('042700', '공급_병목', 0.90, 
   '[{"source_type": "report", "text_excerpt": "연구소 전략 분석: HBM TC 본더 시장의 압도적 지배자. AI 인프라 공급망 내 대체 불가능한 병목 구간 장악.", "date": "2026-05-07"}]', 
   0.95, now())

ON CONFLICT (ticker, category) DO UPDATE SET
  confidence = EXCLUDED.confidence,
  evidence = EXCLUDED.evidence,
  fingerprint_score = EXCLUDED.fingerprint_score,
  detected_at = now(),
  exited_at = NULL;
