-- ============================================================
-- 005: screen_scores에 scores_by_filter JSONB 컬럼 추가
-- Python 스코어링 엔진이 기여 필터별 점수를 저장, 프론트에서 근거 표시에 활용
-- ============================================================

ALTER TABLE screen_scores
  ADD COLUMN IF NOT EXISTS scores_by_filter JSONB;

COMMENT ON COLUMN screen_scores.scores_by_filter IS '필터별 기여 점수 (e.g. {f03: 8.0, f11_rs: 4.2})';
