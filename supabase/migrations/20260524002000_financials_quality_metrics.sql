-- ============================================================
-- financials_q에 품질/효율성 지표용 raw 컬럼 추가
-- 목적: F-Score(Piotroski), accruals(Sloan), GP/Assets(Novy-Marx) 계산
-- ============================================================

ALTER TABLE financials_q
  ADD COLUMN IF NOT EXISTS gross_profit  NUMERIC,   -- 매출총이익 (IS)
  ADD COLUMN IF NOT EXISTS cfo           NUMERIC,   -- 영업활동현금흐름 (CF)
  ADD COLUMN IF NOT EXISTS total_assets  NUMERIC,   -- 자산총계 (BS)
  ADD COLUMN IF NOT EXISTS total_equity  NUMERIC,   -- 자본총계 (BS)
  ADD COLUMN IF NOT EXISTS total_liab    NUMERIC,   -- 부채총계 (BS)
  ADD COLUMN IF NOT EXISTS shares_out    NUMERIC;   -- 유통주식수 (S/CANSLIM)

COMMENT ON COLUMN financials_q.gross_profit IS '매출총이익 = 매출액 - 매출원가 (Novy-Marx GP/A)';
COMMENT ON COLUMN financials_q.cfo IS '영업활동현금흐름 (Sloan accruals = NI - CFO)';
COMMENT ON COLUMN financials_q.total_assets IS '자산총계 (F-Score, GP/A 분모)';
COMMENT ON COLUMN financials_q.total_equity IS '자본총계 (F-Score, D/E 분모)';
COMMENT ON COLUMN financials_q.total_liab IS '부채총계 (F-Score, D/E 분자)';
COMMENT ON COLUMN financials_q.shares_out IS '유통주식수 (O''Neil S, 자사주매입 trend)';
