-- 016_pptr_analysis.sql
-- 라이브러리: PPTR 원인 분석 결과
ALTER TABLE hundredx_library_stocks
  ADD COLUMN IF NOT EXISTS pptr_analysis JSONB;

-- 현재 종목: PPTR 매칭 결과 (어떤 라이브러리 PPTR 패턴과 일치하는지)
ALTER TABLE hundredx_category_matches
  ADD COLUMN IF NOT EXISTS pptr_match JSONB;
