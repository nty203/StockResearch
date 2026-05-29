CREATE TABLE macro_ideas (
  id                              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  date                            DATE NOT NULL,
  title                           TEXT NOT NULL,
  background                      TEXT,
  causal_chain                    TEXT,
  play_mode                       TEXT NOT NULL CHECK (play_mode IN ('Global_Re_rating_Play', 'Domestic_Alternative_Play')),
  total_score                     INTEGER NOT NULL,
  directness                      INTEGER NOT NULL,
  leverage                        INTEGER NOT NULL,
  scalability_or_rotation         INTEGER NOT NULL,
  technical_alignment             INTEGER NOT NULL,
  directness_reason               TEXT,
  leverage_reason                 TEXT,
  scalability_or_rotation_reason  TEXT,
  technical_alignment_reason      TEXT,
  market_timing                   TEXT,
  critical_risk                   TEXT,
  raw_json                        JSONB NOT NULL,
  created_at                      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX ON macro_ideas (date DESC);
CREATE INDEX ON macro_ideas (total_score DESC);
