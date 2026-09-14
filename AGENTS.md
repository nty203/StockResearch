# StockResearch

10배 상승주 조기 발굴 시스템.
프로젝트 전체 구조나 남은 작업 등은 `/project-status` 스킬을 사용하여 확인하세요.

## 중요 코딩/운영 규칙 (항상 준수)

1. **Next.js / Cloudflare**:
   - 모든 route handler 및 page 파일에 `export const runtime = 'edge'` 필수.
   - Node.js 전용 API 절대 사용 금지.
   - Supabase 클라이언트: `@supabase/ssr` + `{ auth: { persistSession: false } }` (edge 호환).

2. **Python / GitHub Actions**:
   - Supabase 연결: pooler URL 사용 (`project.pooler.supabase.com:6543`).
   - 설정값 하드코딩 금지 (`settings_loader.py` 사용).
   - `edgartools` 사용 시 `set_identity` 필수, rate limit 준수.

3. **PPTR 품질 게이트 (A급 조건 완화 금지)**:
   - 후보 생성을 위해 키워드 수, 섹터, OPM 등 임의 조건 완화 금지. 단독 룰(미분류 등) 사용 금지.
   - 라이브러리 종목이 자기 자신의 룰에 매칭 금지.
   - 데이터 누락 판단 전 `data_coverage.py` 로 필수 확인 (`docs/pptr-quality-and-coverage.md` 참고).

4. **스킬(Skill) 관리 및 마이그레이션 규칙**:
   - 스킬 구조를 수정하거나 파일 위치를 이동할 경우, 해당 스킬에 의존하는 **실행 스크립트(.bat 등), 환경변수 경로, 그리고 윈도우 스케줄러(schtasks)** 등의 연결 상태가 깨지지 않는지 반드시 교차 검증하고 업데이트할 것.

5. **Macro-Idea (AI 매크로 엔진) 운용 원칙**:
   - 매크로 아이디어 발굴 시 사전 정의된 테마나 개수에 한계를 두지 말고, 전체 뉴스 원문에서 실질적으로 시장 이슈가 될 만한 모든 트렌드를 빠짐없이 동적으로 추출할 것.
   - 뉴스의 파급력을 판단하기 어렵거나 처음 보는 유형의 이슈인 경우, 반드시 과거에 유사한 뉴스가 발생했을 때 증시와 관련 종목에 어떤 식으로 반영되었는지 분석 및 유추(AI 추론 및 과거 사례 검색)하여 관련 종목(수혜/피해)을 정확하게 도출해 낼 것.
   - AI의 자율적인 추론 능력과 리서치 능력을 최대한 활용하여 깊이 있는 아이디어를 도출할 것.
