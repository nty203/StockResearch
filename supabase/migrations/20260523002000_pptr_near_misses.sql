-- PPTR near misses: partial firings used as self-learning material.

CREATE TABLE IF NOT EXISTS pptr_rule_near_misses (
  id BIGSERIAL PRIMARY KEY,
  rule_id TEXT NOT NULL REFERENCES pptr_rules(rule_id) ON DELETE CASCADE,
  ticker TEXT NOT NULL,
  category TEXT NOT NULL,
  detected_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  near_miss_score NUMERIC(5,3) NOT NULL,
  matched_conditions JSONB NOT NULL DEFAULT '[]'::jsonb,
  missing_conditions JSONB NOT NULL DEFAULT '[]'::jsonb,
  details JSONB NOT NULL DEFAULT '{}'::jsonb,
  UNIQUE(rule_id, ticker, detected_at)
);

CREATE INDEX IF NOT EXISTS idx_pptr_rule_near_misses_rule
  ON pptr_rule_near_misses(rule_id, detected_at DESC);

CREATE INDEX IF NOT EXISTS idx_pptr_rule_near_misses_ticker
  ON pptr_rule_near_misses(ticker, detected_at DESC);
