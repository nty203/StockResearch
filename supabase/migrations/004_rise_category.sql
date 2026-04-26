-- ============================================================
-- 004: 상승 원인 카테고리 필드 추가 (trigger_events)
-- ============================================================

ALTER TABLE trigger_events
  ADD COLUMN IF NOT EXISTS rise_category TEXT;

COMMENT ON COLUMN trigger_events.rise_category IS
  '상승 원인 카테고리: 수주잔고_선행/빅테크_파트너/임상_파이프라인/플랫폼_독점/정책_수혜/수익성_급전환/공급_병목';
