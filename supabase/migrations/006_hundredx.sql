-- 100x Category Detection System
-- Migration 006: hundredx_library_stocks + hundredx_category_matches

-- Historical 100x research library
-- Curated hand-annotated cases from docs/case-study-100x-signal-analysis.md
CREATE TABLE IF NOT EXISTS hundredx_library_stocks (
  id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  ticker               TEXT NOT NULL,
  category             TEXT NOT NULL,       -- rise_category value (7 types)
  pre_rise_signals     JSONB,               -- annotated signal values (bcr_at_signal, opm_delta_at_signal, etc.)
  earliest_signal_date DATE,               -- when the signal was first detectable
  rise_start_date      DATE,               -- when the stock started rising
  peak_multiplier      NUMERIC,            -- actual return (e.g., 20.0 for 20x)
  notes                TEXT,
  created_at           TIMESTAMPTZ DEFAULT now()
);

-- Per-stock category detection results (upserted daily by hundredx scanner)
CREATE TABLE IF NOT EXISTS hundredx_category_matches (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  ticker            TEXT NOT NULL,
  category          TEXT NOT NULL,
  confidence        NUMERIC(4,3) NOT NULL,   -- 0.000–1.000
  evidence          JSONB NOT NULL,           -- [{source_type, source_id, text_excerpt, date, amount}]
  first_detected_at TIMESTAMPTZ,             -- when stock FIRST matched this category (Python-managed)
  detected_at       TIMESTAMPTZ DEFAULT now(),
  exited_at         TIMESTAMPTZ,             -- set when stock no longer matches; cleared on re-entry
  alert_sent_at     TIMESTAMPTZ,             -- set after Telegram alert; prevents duplicate sends
  analog_ticker     TEXT,                    -- closest library stock
  analog_date       DATE,
  analog_multiplier NUMERIC,
  UNIQUE (ticker, category)
);

-- first_detected_at is managed Python-side (not via SQL COALESCE):
--   New entry:     scanner sets first_detected_at = now(), upserts normally
--   Rescan (same): scanner fetches existing first_detected_at, preserves it in upsert row
--   Re-entry:      scanner resets first_detected_at = now() (NEW badge fires again)

CREATE INDEX IF NOT EXISTS idx_hundredx_category
  ON hundredx_category_matches(category, detected_at DESC);

CREATE INDEX IF NOT EXISTS idx_hundredx_ticker
  ON hundredx_category_matches(ticker);

CREATE INDEX IF NOT EXISTS idx_hundredx_first_detected
  ON hundredx_category_matches(first_detected_at DESC);

CREATE INDEX IF NOT EXISTS idx_hundredx_active
  ON hundredx_category_matches(exited_at)
  WHERE exited_at IS NULL;
