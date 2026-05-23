-- PPTR growth engine: rule registry, match ledger, outcomes, and negative cases.

CREATE TABLE IF NOT EXISTS pptr_rules (
  rule_id TEXT PRIMARY KEY,
  library_ticker TEXT NOT NULL,
  producer_id TEXT,
  category TEXT NOT NULL,
  conditions JSONB NOT NULL DEFAULT '{}'::jsonb,
  detector_rule JSONB NOT NULL DEFAULT '{}'::jsonb,
  performance_summary JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_pptr_rules_category
  ON pptr_rules(category);

CREATE TABLE IF NOT EXISTS pptr_rule_matches (
  id BIGSERIAL PRIMARY KEY,
  rule_id TEXT NOT NULL REFERENCES pptr_rules(rule_id) ON DELETE CASCADE,
  ticker TEXT NOT NULL,
  category TEXT NOT NULL,
  matched_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  confidence NUMERIC(5,3) NOT NULL,
  confidence_breakdown JSONB NOT NULL DEFAULT '{}'::jsonb,
  matched_conditions JSONB NOT NULL DEFAULT '[]'::jsonb,
  evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
  as_of_close NUMERIC,
  as_of_market_cap NUMERIC,
  as_of_avg_daily_value NUMERIC,
  UNIQUE(rule_id, ticker, matched_at)
);

CREATE INDEX IF NOT EXISTS idx_pptr_rule_matches_rule_id
  ON pptr_rule_matches(rule_id);

CREATE INDEX IF NOT EXISTS idx_pptr_rule_matches_ticker
  ON pptr_rule_matches(ticker, matched_at DESC);

CREATE TABLE IF NOT EXISTS pptr_rule_performance (
  id BIGSERIAL PRIMARY KEY,
  rule_id TEXT NOT NULL REFERENCES pptr_rules(rule_id) ON DELETE CASCADE,
  evaluated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  horizon_months INTEGER NOT NULL,
  sample_size INTEGER NOT NULL DEFAULT 0,
  avg_return NUMERIC,
  median_return NUMERIC,
  max_drawdown_median NUMERIC,
  hit_rate_2x NUMERIC(5,4),
  hit_rate_5x NUMERIC(5,4),
  hit_rate_10x NUMERIC(5,4),
  hit_rate_30x NUMERIC(5,4),
  hit_rate_100x NUMERIC(5,4),
  false_positive_rate NUMERIC(5,4),
  notes TEXT,
  UNIQUE(rule_id, horizon_months, evaluated_at)
);

CREATE INDEX IF NOT EXISTS idx_pptr_rule_performance_rule_horizon
  ON pptr_rule_performance(rule_id, horizon_months, evaluated_at DESC);

CREATE TABLE IF NOT EXISTS hundredx_negative_cases (
  id BIGSERIAL PRIMARY KEY,
  ticker TEXT NOT NULL,
  category TEXT NOT NULL,
  signal_date DATE NOT NULL,
  failure_type TEXT NOT NULL,
  evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
  notes TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(ticker, category, signal_date, failure_type)
);

CREATE INDEX IF NOT EXISTS idx_hundredx_negative_cases_category
  ON hundredx_negative_cases(category, signal_date DESC);

ALTER TABLE hundredx_category_matches
  ADD COLUMN IF NOT EXISTS pptr_rule_id TEXT,
  ADD COLUMN IF NOT EXISTS pptr_confidence_breakdown JSONB;
