# PPTR 시스템 60점 → 99점 개조 계획

> 목표: out-of-sample Sharpe ≥ 1.5 / MDD ≤ 25% / 5년 annualized return ≥ 25%

## 핵심 진단: 지금 못 버는 7가지 이유
1. ❌ 매수 시점 없음 (detect ≠ buy)
2. ❌ 매도/손절 없음
3. ❌ 포지션 사이징 없음
4. ❌ 거래비용·세금 모델 없음
5. ❌ 유동성 필터 없음
6. ❌ Out-of-sample 검증 없음 (학습=테스트 = 같은 30개)
7. ❌ Confidence calibration 미검증

## Phase 0 — 그라운드 트루스 (4주)
- **0.1** KRX delisted 포함 survivorship-free 10배+ 유니버스 500+개
  - `apps/collector/src/hundredx/data/survivorship_free.py`
- **0.2** Walk-forward purged CV 분할 (Train/Embargo/Val/Embargo/Test)
  - Train: 2000-2018 / Val: 2019-2022 / Test: 2023-현재 (절대 재튜닝 금지)
  - `apps/collector/src/hundredx/ml/walk_forward.py`

## Phase 1 — Detector 개혁 (6주)
- **1.1** LightGBM + monotonic constraints (pptr_confidence.py 교체)
  - `apps/collector/src/hundredx/ml/confidence_model.py`
  - `apps/collector/src/hundredx/ml/feature_builder.py`
- **1.2** Isotonic calibration + Brier score 검증
  - Brier ≤ 0.18 목표
  - `apps/collector/src/hundredx/ml/calibration.py`
- **1.3** Bayesian hierarchical Beta-Binomial base rate
  - `apps/collector/src/hundredx/ml/bayes_base_rate.py`

## Phase 2 — 매매 로직 (8주)
- **2.1** 매수 시점 필터 (유동성/모멘텀/regime)
  - `apps/collector/src/hundredx/trading/entry_filter.py`
- **2.2** 3-tier exit (trailing ATR stop / 손절 / 시간 stop)
  - `apps/collector/src/hundredx/trading/exit_rules.py`
- **2.3** Half-Kelly + vol targeting 포지션 사이징
  - `apps/collector/src/hundredx/trading/position_sizer.py`
- **2.4** 포트폴리오 상태 관리 (카테고리/섹터 집중도, 현금)
  - `apps/collector/src/hundredx/trading/portfolio.py`

## Phase 3 — 백테스트 인프라 (6주)
- **3.1** Event-driven backtester (비용/세금/슬리피지 모델 포함)
  - `apps/collector/src/hundredx/backtest/engine.py`
  - `apps/collector/src/hundredx/backtest/cost_model.py`
- **3.2** 검증 메트릭 (Deflated Sharpe, PBO, Brier, Calmar)
  - `apps/collector/src/hundredx/backtest/metrics.py`
  - Deflated Sharpe ≥ 0.95 AND PBO ≤ 5% 통과 시에만 real money 진행

## Phase 4 — 한국어 NLP 정밀화 (4주)
- **4.1** KR finance domain lexicon (카테고리별 positive/negative keywords)
  - `apps/collector/src/hundredx/data/kr_nlp.py`
- **4.2** DART 공시 메타데이터 features (공시 코드 기반)
  - `apps/collector/src/hundredx/data/dart_meta.py`

## Phase 5 — Paper Trading (6개월)
- **5.1** Paper trading 신호 생성기 + Telegram 통합
  - `apps/collector/src/hundredx/paper_trading/signal_generator.py`
- 중단 기준: 단월 -10% or누적 MDD > 20%

## Phase 6 — Real Money (단계적 12개월)
- Month 1-3: 자본의 5%
- Month 4-6: 20% (paper Sharpe ≥ 1.2 조건)
- Month 7-12: 60%
- Month 13+: 80% 상한 (20%는 영구 현금)
- Kill switch: 단월 -15% / 누적 MDD > 30% / 60d Sharpe < 0

## 점수 로드맵

| 섹션 | 현재 | 목표 | 핵심 조치 |
|---|---|---|---|
| A. 패턴 매칭 | 3/5 | 5/5 | Phase 0.1 (500+) |
| B. Trigger timeline | 4/5 | 5/5 | Phase 1.1 event study 명시적 모델링 |
| C. 정량 시그널 | 4/5 | 5/5 | LightGBM + NLP |
| D. 신뢰도 모델 | 2.5/5 | 5/5 | Calibration + Bayesian |
| E. Self-learning | 3/5 | 5/5 | Out-of-sample feedback + drift detection |
| F. Base rate | 2.5/5 | 5/5 | Bayesian hierarchical |
| G. 결함 회피 | 2/5 | 5/5 | Purged CV + Deflated Sharpe + Paper |
| 매매 로직 | 0 | — | Phase 2 전체 |
| **종합** | **21/35** | **35/35** | |

## DB 신규 테이블
- `pptr_training_samples` — 학습 데이터셋 (features + label)
- `pptr_model_versions` — 모델 버전 관리
- `backtest_runs` — 백테스트 결과 이력
- `paper_trades` — 페이퍼 트레이딩 기록
- `portfolio_snapshots` — 포트폴리오 스냅샷

## 타임라인
```
Week  1-4:  Phase 0 (데이터 + 분할)
Week  5-10: Phase 1 (LightGBM + Calibration)
Week 11-18: Phase 2 (매매 로직)
Week 19-24: Phase 3 (백테스트)
Week 25-28: Phase 4 (NLP)
Week 29-52: Phase 5 (Paper trading)
Week 53+:   Phase 6 (Real money)
```

## 핵심 참고 자료
- López de Prado, *Advances in Financial Machine Learning* (Wiley, 2018) — Ch.7 purged CV, Ch.14 Deflated Sharpe
- Bailey & López de Prado, "The Deflated Sharpe Ratio" (SSRN 2460551)
- Gervais-Kaniel-Mingelgrin (2001), *J Finance* — High-Volume Return Premium
- Novy-Marx (2013), *JFE* — Gross Profitability
- MacLean-Thorp-Ziemba (2010) — Half-Kelly
- Loughran-McDonald (2011), *J Finance* — Finance NLP lexicon
