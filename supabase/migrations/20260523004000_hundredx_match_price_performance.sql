-- Store recent price performance for active 100x signal matches.
-- Multipliers are decimals (10.0 = 10x). Percent fields use investment-return
-- convention: 10x = +900%, not +1000%.

ALTER TABLE hundredx_category_matches
  ADD COLUMN IF NOT EXISTS price_baseline_date DATE,
  ADD COLUMN IF NOT EXISTS price_baseline_close NUMERIC,
  ADD COLUMN IF NOT EXISTS price_latest_date DATE,
  ADD COLUMN IF NOT EXISTS price_latest_close NUMERIC,
  ADD COLUMN IF NOT EXISTS price_peak_date DATE,
  ADD COLUMN IF NOT EXISTS price_peak_close NUMERIC,
  ADD COLUMN IF NOT EXISTS price_current_multiplier NUMERIC,
  ADD COLUMN IF NOT EXISTS price_change_pct NUMERIC,
  ADD COLUMN IF NOT EXISTS price_peak_multiplier NUMERIC,
  ADD COLUMN IF NOT EXISTS price_peak_change_pct NUMERIC,
  ADD COLUMN IF NOT EXISTS price_performance_updated_at TIMESTAMPTZ;

COMMENT ON COLUMN hundredx_category_matches.price_current_multiplier IS
  'Latest close divided by the recent-window baseline close. Example: 10.0 means 10x.';
COMMENT ON COLUMN hundredx_category_matches.price_change_pct IS
  'Return from baseline to latest close: (multiplier - 1) * 100. Example: 10x = +900%.';
COMMENT ON COLUMN hundredx_category_matches.price_peak_multiplier IS
  'Highest close after baseline divided by baseline close.';
COMMENT ON COLUMN hundredx_category_matches.price_peak_change_pct IS
  'Return from baseline to peak close: (peak_multiplier - 1) * 100.';

CREATE INDEX IF NOT EXISTS idx_hundredx_active_price_change
  ON hundredx_category_matches(price_change_pct DESC)
  WHERE exited_at IS NULL;
