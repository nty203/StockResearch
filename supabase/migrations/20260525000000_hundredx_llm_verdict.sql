-- LLM 검증 결과를 컬럼으로 노출 (evidence JSONB에서 추출 필요 없게)
ALTER TABLE hundredx_category_matches
  ADD COLUMN IF NOT EXISTS llm_verdict TEXT
    CHECK (llm_verdict IN ('confirm', 'reject', 'uncertain')),
  ADD COLUMN IF NOT EXISTS llm_verdict_at TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS idx_hundredx_matches_llm_verdict
  ON hundredx_category_matches (llm_verdict)
  WHERE llm_verdict IS NOT NULL;

-- 기존 evidence에서 verdict 백필 (가장 최근 LLM 판정만 사용)
WITH latest_verdicts AS (
  SELECT
    m.id,
    CASE
      WHEN ev->>'text_excerpt' LIKE 'LLM confirm%' THEN 'confirm'
      WHEN ev->>'text_excerpt' LIKE 'LLM reject%' THEN 'reject'
      WHEN ev->>'text_excerpt' LIKE 'LLM uncertain%' THEN 'uncertain'
    END AS verdict,
    ev->>'date' AS verdict_date,
    ROW_NUMBER() OVER (PARTITION BY m.id ORDER BY ev->>'date' DESC NULLS LAST) AS rn
  FROM hundredx_category_matches m,
       jsonb_array_elements(COALESCE(m.evidence, '[]'::jsonb)) ev
  WHERE ev->>'source_type' = 'llm_verdict'
)
UPDATE hundredx_category_matches m
SET llm_verdict = lv.verdict,
    llm_verdict_at = lv.verdict_date::timestamptz
FROM latest_verdicts lv
WHERE m.id = lv.id AND lv.rn = 1 AND lv.verdict IS NOT NULL;
