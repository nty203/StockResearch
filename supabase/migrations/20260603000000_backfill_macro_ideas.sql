-- 기존 macro_ideas 데이터 품질 개선
-- 1) theme=NULL 레코드에 테마 자동 태깅
-- 2) candidates.early_signal_score / signal_flag 역산 보정

-- ① theme 태깅 (제목 키워드 기반)
UPDATE macro_ideas
SET theme = CASE
  WHEN title ILIKE '%MLCC%' OR title ILIKE '%FC-BGA%' OR title ILIKE '%기판%' OR title ILIKE '%삼성전기%'
       THEN '전자부품/AI기판'
  WHEN title ILIKE '%HBM%' OR title ILIKE '%반도체%' OR title ILIKE '%SK하이닉스%' OR title ILIKE '%한미반도체%'
       THEN 'AI반도체/HBM'
  WHEN title ILIKE '%조선%' OR title ILIKE '%방산%' OR title ILIKE '%LNG%' OR title ILIKE '%한화에어로%'
       THEN '조선/방산'
  WHEN title ILIKE '%로봇%' OR title ILIKE '%피지컬AI%' OR title ILIKE '%피지컬 AI%' OR title ILIKE '%현대로템%'
       THEN '로봇/피지컬AI'
  WHEN title ILIKE '%비상발전%' OR title ILIKE '%전력%' OR title ILIKE '%원전%' OR title ILIKE '%데이터센터 발전%'
       THEN '원전/전력'
  WHEN title ILIKE '%K뷰티%' OR title ILIKE '%ODM%' OR title ILIKE '%백화점%' OR title ILIKE '%명품%'
       THEN '내수소비/유통/명품'
  WHEN title ILIKE '%밸류업%' OR title ILIKE '%금융%' OR title ILIKE '%배당%'
       THEN '금융/밸류업'
  WHEN title ILIKE '%바이오%' OR title ILIKE '%제약%' OR title ILIKE '%임상%'
       THEN '바이오/제약'
  WHEN title ILIKE '%2차전지%' OR title ILIKE '%배터리%' OR title ILIKE '%ESS%'
       THEN '2차전지/ESS'
  ELSE theme
END
WHERE theme IS NULL;

-- ② candidates 내 early_signal_score / signal_flag 역산 보정
-- near_52w_high, ret_1m, ret_3m이 존재하는 candidates에 한해
-- 스코어 공식: early(n52 기반) - penalty(r3>60 초과분/2) + bonus(r1 0~15 캡)
UPDATE macro_ideas
SET candidates = (
  SELECT jsonb_agg(
    CASE
      WHEN (c->>'early_signal_score') IS NOT NULL THEN c  -- 이미 있으면 유지
      WHEN (c->>'near_52w_high') IS NOT NULL THEN
        c || jsonb_build_object(
          'early_signal_score',
          GREATEST(0, ROUND(
            CASE
              WHEN (c->>'near_52w_high')::float BETWEEN 88 AND 99  THEN 50
              WHEN (c->>'near_52w_high')::float BETWEEN 99 AND 112 THEN 40
              WHEN (c->>'near_52w_high')::float > 112              THEN 30
              WHEN (c->>'near_52w_high')::float BETWEEN 80 AND 88  THEN 30
              ELSE 20
            END
            - LEAST(30, GREATEST(0, COALESCE((c->>'ret_3m')::float, 0) - 60) / 2)
            + LEAST(15, GREATEST(0, COALESCE((c->>'ret_1m')::float, 0)))
          , 1)),
          'signal_flag',
          CASE
            WHEN (c->>'near_52w_high')::float BETWEEN 88 AND 99  THEN '🔺임박'
            WHEN (c->>'near_52w_high')::float BETWEEN 99 AND 112 THEN '✅돌파직후'
            WHEN (c->>'near_52w_high')::float > 112              THEN '⚠️과열'
            WHEN (c->>'near_52w_high')::float BETWEEN 80 AND 88  THEN '📌중기후보'
            ELSE '🔵하단'
          END
        )
      ELSE c
    END
  )
  FROM jsonb_array_elements(candidates) AS c
)
WHERE candidates IS NOT NULL
  AND jsonb_array_length(candidates) > 0
  AND EXISTS (
    SELECT 1 FROM jsonb_array_elements(candidates) c2
    WHERE (c2->>'early_signal_score') IS NULL
      AND (c2->>'near_52w_high') IS NOT NULL
  );

-- ③ 검증 쿼리 (실행 확인용)
-- SELECT date, theme, title FROM macro_ideas ORDER BY date DESC;
