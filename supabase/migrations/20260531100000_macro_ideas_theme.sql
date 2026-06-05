ALTER TABLE macro_ideas ADD COLUMN IF NOT EXISTS theme TEXT CHECK (
  theme IS NULL OR theme IN (
    'AI반도체/HBM',
    '전자부품/AI기판',
    '내수소비/유통/명품',
    '조선/방산',
    '바이오/제약',
    '2차전지/ESS',
    '금융/밸류업',
    '로봇/피지컬AI',
    '원전/전력'
  )
);

CREATE INDEX IF NOT EXISTS macro_ideas_theme_idx ON macro_ideas (theme);
