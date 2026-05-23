-- 카테고리 중복 오염 데이터 정리
-- 원인: PPTR quant-only 매칭이 키워드 증거 없이 모든 카테고리 0.750으로 발화
-- 결과: 단일 종목이 7-8개 카테고리 동시 활성 → 신호 품질 저하

-- 1단계: 노이즈 카테고리(미분류, 단기_테마_급등) 전량 종료
UPDATE hundredx_category_matches
SET exited_at = NOW()
WHERE category IN ('미분류', '단기_테마_급등')
  AND exited_at IS NULL;

-- 2단계: 동일 종목 > 2개 활성 카테고리 → always-keep + 최고신뢰 1개만 유지
-- always-keep: 임상_파이프라인, 수익성_급전환
-- 나머지 비-always-keep 중 신뢰도 최고 1개 유지, 나머지 종료
UPDATE hundredx_category_matches
SET exited_at = NOW()
WHERE exited_at IS NULL
  AND category NOT IN ('임상_파이프라인', '수익성_급전환')
  AND (ticker, category) NOT IN (
    -- 비-always-keep 중 신뢰도 최고 (동점이면 최근 탐지) 1개 선택
    SELECT DISTINCT ON (ticker) ticker, category
    FROM hundredx_category_matches
    WHERE exited_at IS NULL
      AND category NOT IN ('임상_파이프라인', '수익성_급전환', '미분류', '단기_테마_급등')
    ORDER BY ticker, confidence DESC, detected_at DESC
  )
  AND ticker IN (
    -- 3개 초과 활성 카테고리 보유 종목만 정리 대상
    SELECT ticker
    FROM hundredx_category_matches
    WHERE exited_at IS NULL
    GROUP BY ticker
    HAVING COUNT(*) > 2
  );
