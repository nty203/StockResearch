-- 중복 pptr_rule_matches 정리: (rule_id, ticker) 조합별 최신 1건만 유지.
-- 이 마이그레이션은 scanner.py insert→upsert 전환 전 누적된 중복행을 제거.

DELETE FROM pptr_rule_matches
WHERE id NOT IN (
  SELECT DISTINCT ON (rule_id, ticker) id
  FROM pptr_rule_matches
  ORDER BY rule_id, ticker, matched_at DESC
);

-- 중복 pptr_rule_near_misses 정리: (rule_id, ticker) 조합별 최신 1건만 유지.

DELETE FROM pptr_rule_near_misses
WHERE id NOT IN (
  SELECT DISTINCT ON (rule_id, ticker) id
  FROM pptr_rule_near_misses
  ORDER BY rule_id, ticker, detected_at DESC
);
