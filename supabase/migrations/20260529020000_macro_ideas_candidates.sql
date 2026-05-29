-- 가설별 밸류체인 후보주를 영속화. 스킬이 가설 도출 후 후보를 추출해 저장,
-- /macro-ideas 대시보드가 각 가설 카드에 Top 후보를 표시한다.
-- 구조: [{ticker, name, role, near_52w_high, ret_1m, ret_3m, momentum, hundredx_match}]
ALTER TABLE macro_ideas ADD COLUMN candidates JSONB DEFAULT '[]'::jsonb;
