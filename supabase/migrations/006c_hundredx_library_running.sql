-- 006c: 라이브러리 종목의 "현재 시점 기준 배수" 추적 컬럼
-- 주기적 업데이트로 100배에 점진 수렴하는 시스템 지원
--
-- peak_multiplier      : seed 시점에 기록한 historical 최고 배수 (정적)
-- latest_multiplier    : 가장 최근 업데이트의 현재가 기반 배수 (rise_start_date → 오늘)
-- price_at_rise_start  : rise_start_date 시점의 종가 (배수 계산 분모)
-- latest_updated_at    : update_library 스크립트 마지막 실행 시각

ALTER TABLE hundredx_library_stocks
  ADD COLUMN IF NOT EXISTS price_at_rise_start  NUMERIC,
  ADD COLUMN IF NOT EXISTS latest_multiplier    NUMERIC,
  ADD COLUMN IF NOT EXISTS latest_updated_at    TIMESTAMPTZ;

COMMENT ON COLUMN hundredx_library_stocks.peak_multiplier      IS 'Historical peak multiplier (한 번 기록 후 정적, seed 또는 수동 갱신)';
COMMENT ON COLUMN hundredx_library_stocks.latest_multiplier    IS '오늘 시점 기준 배수 (rise_start_date 가격 대비 최신가). 주기 업데이트 스크립트가 채움.';
COMMENT ON COLUMN hundredx_library_stocks.price_at_rise_start  IS 'rise_start_date 시점의 종가 — latest_multiplier 분모';
COMMENT ON COLUMN hundredx_library_stocks.latest_updated_at    IS 'latest_multiplier가 마지막으로 갱신된 시각';
