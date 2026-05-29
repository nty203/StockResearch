-- 매크로 뉴스 피드 — 종목 태그 없이 경제/정책/산업 전반 뉴스를 누적.
-- news 테이블(ticker NOT NULL, hundredx 종목별 시그널용)과 분리하여
-- macro-idea 가설 도출의 탑다운 입력으로 사용한다.
CREATE TABLE macro_news (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  source       TEXT NOT NULL,
  published_at TIMESTAMPTZ NOT NULL,
  url          TEXT NOT NULL UNIQUE,
  title        TEXT NOT NULL,
  summary      TEXT,
  category     TEXT,          -- 정책/금리환율/소비/산업/원자재/실적/기타
  lang         TEXT NOT NULL DEFAULT 'ko' CHECK (lang IN ('ko','en')),
  created_at   TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX ON macro_news (published_at DESC);
CREATE INDEX ON macro_news (category, published_at DESC);
