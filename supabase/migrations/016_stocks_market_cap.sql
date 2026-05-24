-- ============================================================
-- 시가총액(market_cap) 컬럼 추가
-- 출처: FinanceDataReader StockListing Marcap 컬럼 (원 단위, KRW)
-- 활용: 소형주 필터 (100배 전제조건), ML feature_builder fcf_yield 분모
-- ============================================================
ALTER TABLE stocks ADD COLUMN IF NOT EXISTS market_cap BIGINT;

COMMENT ON COLUMN stocks.market_cap IS '시가총액 (원 단위, FinanceDataReader Marcap 기준, 매일 갱신)';
