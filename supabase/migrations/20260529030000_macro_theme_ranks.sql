-- 매일 테마 랭킹 스냅샷 저장 — 어제 대비 순위 변화·신규 정렬 종목 감지에 사용
CREATE TABLE macro_theme_ranks (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  run_date    DATE NOT NULL,
  theme       TEXT NOT NULL,
  rank        INTEGER NOT NULL,
  score       NUMERIC(6,2) NOT NULL,
  aligned     INTEGER NOT NULL DEFAULT 0,   -- 52w신고가권+3M양수 종목 수
  candidates  JSONB NOT NULL DEFAULT '[]',  -- 모멘텀 랭킹 후보주
  run_at      TIMESTAMPTZ DEFAULT now(),
  UNIQUE (run_date, theme)
);
CREATE INDEX ON macro_theme_ranks (run_date DESC);
CREATE INDEX ON macro_theme_ranks (theme, run_date DESC);
