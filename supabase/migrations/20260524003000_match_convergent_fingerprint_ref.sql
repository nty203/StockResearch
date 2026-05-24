-- Scanner가 산출하는 신규 보조 메타데이터 컬럼 추가
ALTER TABLE hundredx_category_matches
  ADD COLUMN IF NOT EXISTS fingerprint_library_ticker TEXT,
  ADD COLUMN IF NOT EXISTS convergent_signals JSONB;

COMMENT ON COLUMN hundredx_category_matches.fingerprint_library_ticker IS '가장 닮은 라이브러리 100배 종목 ticker (fingerprint_match 결과)';
COMMENT ON COLUMN hundredx_category_matches.convergent_signals IS '인사이더 매수/자사주 매입 신호 라벨 배열 (예: ["insider_buy×2", "buyback×1"])';
