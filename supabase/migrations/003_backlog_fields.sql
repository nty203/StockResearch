-- ============================================================
-- 003: 수주잔고 필드 추가 (f13/f14 필터 지원)
-- ============================================================

ALTER TABLE financials_q
  ADD COLUMN IF NOT EXISTS order_backlog      NUMERIC,
  ADD COLUMN IF NOT EXISTS order_backlog_prev NUMERIC;

-- 기존 stocks 테이블에 섹터 태그 추가 (섹터-이벤트 매핑용)
ALTER TABLE stocks
  ADD COLUMN IF NOT EXISTS sector_tag TEXT;

COMMENT ON COLUMN financials_q.order_backlog      IS '수주잔고 (단위: 원)';
COMMENT ON COLUMN financials_q.order_backlog_prev IS '전기 수주잔고 (YoY 성장률 계산용)';
COMMENT ON COLUMN stocks.sector_tag               IS '섹터 태그 (방산/전력기기/바이오/로봇/원전 등)';
