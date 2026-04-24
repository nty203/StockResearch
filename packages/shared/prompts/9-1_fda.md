# 프롬프트 9-1: FDA / 바이오 섹터 전문 분석

## 목적 (적용 섹터: 바이오·제약·의료기기)
FDA 승인 파이프라인과 임상 데이터를 분석하여, 규제 이벤트 기반 카탈리스트를 평가한다.

## 분석 지시

아래 데이터를 바탕으로 다음을 분석하세요:

### 1. 파이프라인 평가
- 현재 임상 단계별 파이프라인 (Phase 1/2/3 / NDA·BLA 제출)
- 각 후보 물질의 적응증(indication)과 시장 규모
- 임상 성공 확률 (업계 평균: P1→P2 63%, P2→P3 29%, P3→승인 58%)

### 2. FDA 인터랙션 히스토리
- 최근 FDA 미팅 결과 (Type A/B/C)
- Breakthrough Therapy / Fast Track 지정 여부
- CRL (Complete Response Letter) 이력

### 3. 규제 타임라인
- PDUFA 날짜 (FDA 결정 기한)
- 향후 12개월 내 결정 예정 후보 물질
- EU EMA 병행 검토 여부

### 4. 상업화 역량
- 승인 후 시판 계획 (자체 영업 vs 파트너링)
- 보험 급여 전략 (coverage & reimbursement)
- 경쟁 제품 대비 임상 우월성 데이터

### 5. 실패 시나리오
- 주력 파이프라인 실패 시 주가 영향 (선례 사례 기반 추정)
- 현금 런웨이 (burn rate × 현금잔고)

## 출력 형식 (JSON)
```json
{
  "pipeline_value": "높음",
  "key_pdufa_dates": ["2024-Q3: XXX-001 NDA", "2025-Q1: YYY-002 BLA"],
  "success_probability_weighted": 0.42,
  "cash_runway_months": 18,
  "fda_catalyst_score": 7,
  "fda_summary": "3개 후보 물질 중 2개 Breakthrough 지정, 2024 Q3 PDUFA 최대 관전포인트"
}
```
