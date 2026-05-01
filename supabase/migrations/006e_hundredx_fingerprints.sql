-- 006e: 라이브러리 종목의 "상승 직전 fingerprint" 인코딩
-- 각 100배+ 종목의 rise_start_date 직전에 실제로 관측된 신호를 구조화 JSONB로 저장.
-- 디텍터는 현재 종목과 이 fingerprint를 비교해 유사도 점수를 계산한다.
--
-- pre_rise_signals 스키마:
-- {
--   "quant": {                      -- 정량 신호 (financials 비교)
--     "bcr_at_signal": 2.8,         -- 수주잔고 / 매출
--     "backlog_yoy_pct": 115,       -- 수주잔고 전년비 성장률
--     "opm_at_signal": 2.8,         -- 시그널 시점 영업이익률 (%)
--     "opm_prev": 1.2,              -- 전기 영업이익률 (전환 폭 계산)
--     "revenue_growth_yoy": 50      -- 매출 YoY (%)
--   },
--   "keywords": ["폴란드","K-9",...],  -- 공시/뉴스 매치 키워드 셋
--   "min_keyword_matches": 3,        -- 최소 매칭 임계값
--   "amount_threshold_billions": 1000, -- 단건 또는 누계 금액 임계 (억 단위)
--   "sector_required": "방산",        -- 섹터 일치 필요 여부
--   "lead_months": 12,               -- 상승 시작까지 선행 기간
--   "special": {                     -- 특수 패턴 (콜옵션, 빅테크 지분 등)
--     "callopt": true,
--     "bigtech": "NVIDIA",
--     "vertical_complete": true
--   }
-- }
--
-- 출처: docs/case-study-100x-signal-analysis.md + docs/signal-expansion-plan.md

-- ── 한화에어로스페이스 ────────────────────────────────────────────────────
UPDATE hundredx_library_stocks SET pre_rise_signals = '{
  "quant": {"bcr_at_signal": 2.8, "backlog_yoy_pct": 115, "opm_at_signal": 2.8, "opm_prev": 1.2},
  "keywords": ["폴란드", "K-9", "K-2", "FA-50", "NATO", "방산", "수출", "조원", "Redback"],
  "min_keyword_matches": 3,
  "amount_threshold_billions": 9000,
  "sector_required": "방산",
  "lead_months": 12,
  "special": {"large_export_contract": true}
}'::jsonb WHERE ticker = '012450' AND category = '수주잔고_선행';

UPDATE hundredx_library_stocks SET pre_rise_signals = '{
  "keywords": ["폴란드", "NATO", "방산", "수출", "재무장", "K-9", "Redback"],
  "min_keyword_matches": 2,
  "sector_required": "방산",
  "lead_months": 12,
  "special": {"geopolitical_event": "Ukraine_war"}
}'::jsonb WHERE ticker = '012450' AND category = '정책_수혜';

-- ── HD현대일렉트릭 ────────────────────────────────────────────────────────
UPDATE hundredx_library_stocks SET pre_rise_signals = '{
  "quant": {"bcr_at_signal": 1.4, "backlog_yoy_pct": 100, "opm_at_signal": 3.0, "opm_prev": 1.0},
  "keywords": ["HVDC", "변압기", "미국", "전력망", "수주", "GIS", "초고압"],
  "min_keyword_matches": 3,
  "amount_threshold_billions": 500,
  "sector_required": "전력기기",
  "lead_months": 9
}'::jsonb WHERE ticker = '267260' AND category = '수주잔고_선행';

UPDATE hundredx_library_stocks SET pre_rise_signals = '{
  "keywords": ["IRA", "미국", "전력망", "AI 데이터센터", "리쇼어링", "에너지 안보"],
  "min_keyword_matches": 2,
  "sector_required": "전력기기",
  "lead_months": 9,
  "special": {"policy_event": "IRA_Inflation_Reduction_Act"}
}'::jsonb WHERE ticker = '267260' AND category = '정책_수혜';

-- ── 효성중공업 ────────────────────────────────────────────────────────────
UPDATE hundredx_library_stocks SET pre_rise_signals = '{
  "quant": {"bcr_at_signal": 1.0, "backlog_yoy_pct": 50, "opm_at_signal": 2.5, "opm_prev": 1.5},
  "keywords": ["HVDC", "GIS", "변압기", "중공업", "수출", "전력기자재"],
  "min_keyword_matches": 2,
  "sector_required": "전력기기",
  "lead_months": 9
}'::jsonb WHERE ticker = '298040' AND category = '수주잔고_선행';

UPDATE hundredx_library_stocks SET pre_rise_signals = '{
  "quant": {"opm_delta_at_signal": 6.0, "opm_prev": 2.0, "opm_at_signal": 8.0},
  "keywords": ["수익성", "흑자", "턴어라운드", "OPM", "영업이익률"],
  "min_keyword_matches": 1,
  "lead_months": 9
}'::jsonb WHERE ticker = '298040' AND category = '수익성_급전환';

-- ── 에코프로 (실제 100배+ 종목) ───────────────────────────────────────────
UPDATE hundredx_library_stocks SET pre_rise_signals = '{
  "quant": {"revenue_growth_yoy": 40, "opm_at_signal": 5.0, "opm_prev": 2.0},
  "keywords": ["양극재", "EV 배터리", "공급 부족", "리튬", "IRA", "양산", "증설", "CAPEX"],
  "min_keyword_matches": 3,
  "sector_required": "양극재",
  "lead_months": 24,
  "special": {"capex_surge": true, "policy_event": "IRA_보조금"}
}'::jsonb WHERE ticker = '086520' AND category = '공급_병목';

-- ── 한미반도체 ────────────────────────────────────────────────────────────
UPDATE hundredx_library_stocks SET pre_rise_signals = '{
  "keywords": ["TC본더", "HBM", "글로벌 유일", "특허", "양산", "수율", "SK하이닉스"],
  "min_keyword_matches": 3,
  "sector_required": "반도체장비",
  "lead_months": 12,
  "special": {"global_sole_supplier": true}
}'::jsonb WHERE ticker = '042700' AND category = '플랫폼_독점';

UPDATE hundredx_library_stocks SET pre_rise_signals = '{
  "keywords": ["NVIDIA", "HBM", "TC본더", "수주", "공급 계약", "SK하이닉스"],
  "min_keyword_matches": 3,
  "sector_required": "반도체장비",
  "lead_months": 12,
  "special": {"bigtech": "NVIDIA"}
}'::jsonb WHERE ticker = '042700' AND category = '빅테크_파트너';

-- ── 알테오젠 ──────────────────────────────────────────────────────────────
UPDATE hundredx_library_stocks SET pre_rise_signals = '{
  "keywords": ["SC 플랫폼", "Hybrozyme", "히알루로니다제", "FDA IND", "기술이전", "빅파마", "license out", "마일스톤"],
  "min_keyword_matches": 3,
  "amount_threshold_billions": 1000,
  "sector_required": "바이오",
  "lead_months": 18,
  "special": {"big_pharma_deal": true}
}'::jsonb WHERE ticker = '196170' AND category = '임상_파이프라인';

-- ── 로보티즈 ──────────────────────────────────────────────────────────────
UPDATE hundredx_library_stocks SET pre_rise_signals = '{
  "keywords": ["Dynamixel", "휴머노이드", "humanoid", "액추에이터", "학술", "오픈AI", "구글", "로봇"],
  "min_keyword_matches": 2,
  "sector_required": "로봇",
  "lead_months": 18,
  "special": {"academic_adoption": true}
}'::jsonb WHERE ticker = '108490' AND category = '플랫폼_독점';

UPDATE hundredx_library_stocks SET pre_rise_signals = '{
  "keywords": ["LG전자", "지분 취득", "전략적 투자", "유상증자 참여", "휴머노이드", "Dynamixel"],
  "min_keyword_matches": 2,
  "amount_threshold_billions": 90,
  "sector_required": "로봇",
  "lead_months": 18,
  "special": {"bigtech": "LG전자", "strategic_stake": true}
}'::jsonb WHERE ticker = '108490' AND category = '빅테크_파트너';

-- ── 대한광통신 ────────────────────────────────────────────────────────────
UPDATE hundredx_library_stocks SET pre_rise_signals = '{
  "keywords": ["광섬유", "광케이블", "모재", "수직계열화", "AI 데이터센터", "빅테크", "864심"],
  "min_keyword_matches": 3,
  "sector_required": "광통신",
  "lead_months": 24,
  "special": {"vertical_complete": true}
}'::jsonb WHERE ticker = '010170' AND category = '플랫폼_독점';

UPDATE hundredx_library_stocks SET pre_rise_signals = '{
  "keywords": ["광섬유", "AI 데이터센터", "공급 부족", "수요 폭발", "납기"],
  "min_keyword_matches": 2,
  "sector_required": "광통신",
  "lead_months": 24
}'::jsonb WHERE ticker = '010170' AND category = '공급_병목';

-- ── 삼천당제약 ────────────────────────────────────────────────────────────
UPDATE hundredx_library_stocks SET pre_rise_signals = '{
  "keywords": ["GLP-1", "S-PASS", "경구형", "기술이전", "일본", "유럽", "라이선스", "마일스톤", "세마글루타이드"],
  "min_keyword_matches": 3,
  "amount_threshold_billions": 5000,
  "sector_required": "바이오",
  "lead_months": 18,
  "special": {"sequential_tech_transfer": true}
}'::jsonb WHERE ticker = '000250' AND category = '임상_파이프라인';

-- ── 레인보우로보틱스 ──────────────────────────────────────────────────────
UPDATE hundredx_library_stocks SET pre_rise_signals = '{
  "keywords": ["삼성전자", "유상증자 참여", "콜옵션", "call option", "전략적 투자", "최대주주", "휴머노이드"],
  "min_keyword_matches": 2,
  "amount_threshold_billions": 590,
  "sector_required": "로봇",
  "lead_months": 0,
  "special": {"bigtech": "삼성전자", "callopt": true, "strategic_stake": true}
}'::jsonb WHERE ticker = '277810' AND category = '빅테크_파트너';

-- ── 펩트론 ────────────────────────────────────────────────────────────────
UPDATE hundredx_library_stocks SET pre_rise_signals = '{
  "keywords": ["SmartDepo", "FDA IND", "LG화학", "CDMO", "GLP-1", "신공장", "임상", "유통 계약"],
  "min_keyword_matches": 3,
  "sector_required": "바이오",
  "lead_months": 18,
  "special": {"new_factory": true, "cdmo_partner": "LG화학"}
}'::jsonb WHERE ticker = '087010' AND category = '임상_파이프라인';

-- ── 우리기술 ──────────────────────────────────────────────────────────────
UPDATE hundredx_library_stocks SET pre_rise_signals = '{
  "keywords": ["원전", "MMIS", "체코", "두코바니", "탈원전", "정책 전환", "원안위", "인증"],
  "min_keyword_matches": 3,
  "sector_required": "원전",
  "lead_months": 12,
  "special": {"policy_event": "탈원전_철회", "cert_renewed": true}
}'::jsonb WHERE ticker = '032820' AND category = '정책_수혜';

UPDATE hundredx_library_stocks SET pre_rise_signals = '{
  "quant": {"bcr_at_signal": 3.0, "backlog_yoy_pct": 80},
  "keywords": ["원전", "MMIS", "체코", "두코바니", "수주", "수주잔고"],
  "min_keyword_matches": 3,
  "sector_required": "원전",
  "lead_months": 12
}'::jsonb WHERE ticker = '032820' AND category = '수주잔고_선행';

-- 매칭 결과를 저장할 컬럼 추가
ALTER TABLE hundredx_category_matches
  ADD COLUMN IF NOT EXISTS fingerprint_score      NUMERIC(4,3),  -- 0-1, 라이브러리 패턴과 유사도
  ADD COLUMN IF NOT EXISTS fingerprint_dims       JSONB;          -- {matched: [...], missing: [...], details: {...}}

COMMENT ON COLUMN hundredx_category_matches.fingerprint_score IS '라이브러리 fingerprint와의 유사도 (0-1) — 100배 종목 패턴과 얼마나 닮았는지';
COMMENT ON COLUMN hundredx_category_matches.fingerprint_dims  IS '매칭 차원 상세: {matched_quant, missing_quant, matched_keywords, missing_keywords, sector_match}';
