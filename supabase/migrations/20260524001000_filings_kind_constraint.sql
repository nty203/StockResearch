-- 2026-05-24: filings 테이블 개선
-- 1) source CHECK 확장: KIND, SEED 소스 허용
-- 2) (ticker, filed_at, filing_type) unique constraint 추가 (upsert 지원)

-- source CHECK 확장
ALTER TABLE filings
  DROP CONSTRAINT IF EXISTS filings_source_check;

ALTER TABLE filings
  ADD CONSTRAINT filings_source_check
  CHECK (source IN ('DART', 'SEC', 'KIND', 'SEED'));

-- unique constraint for upsert (ticker + filed_at + filing_type)
ALTER TABLE filings
  DROP CONSTRAINT IF EXISTS filings_ticker_filed_at_type_key;

ALTER TABLE filings
  ADD CONSTRAINT filings_ticker_filed_at_type_key
  UNIQUE (ticker, filed_at, filing_type);
