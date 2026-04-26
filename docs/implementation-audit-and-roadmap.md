# 구현 감사 및 개선 로드맵

> 작성일: 2026-04-26
> 기준 커밋: main 브랜치 최신 상태

---

## 1. 구현 완료 현황 (Phase별)

### Phase 0–4 (Python + 백엔드) — 98% 완료

| 컴포넌트 | 파일 | 상태 | 비고 |
|---|---|---|---|
| 유니버스 수집 | universe.py | ✅ 완료 | KOSPI/KOSDAQ/S&P1500 |
| 가격 수집 | prices.py | ✅ 완료 | KR(FDR) + US(yfinance) |
| 한국 재무 | financials_dart.py | ✅ 완료 | DART OpenAPI, 분기별 |
| 미국 재무 | financials_sec.py | ✅ 완료 | edgartools, SEC EDGAR |
| 공시 감시 | filings_watch.py | ✅ 완료 | DART + SEC 8-K |
| 뉴스 RSS | news_rss.py | ✅ 완료 | 한경/조선비즈/Yahoo |
| Supabase 유틸 | upsert.py | ✅ 완료 | 배치 upsert, pipeline_run |
| 한국 필터 | filters_kr.py | ✅ 완료 | f01–f12, None 관대 처리 |
| 미국 필터 | filters_us.py | ✅ 완료 | us01–us15 |
| 통합 점수 | score.py | ⚠️ 버그 있음 | 아래 상세 설명 |
| 피크 리스크 | peak_risk.py | ✅ 완료 | -30점 패널티 |
| 설정 로더 | settings_loader.py | ✅ 완료 | Supabase settings 테이블 |
| 트리거 분류기 | classifier.py | ✅ 완료 | 15개 유형, 신뢰도 점수 |
| 골든 시그널 | golden_signal.py | ✅ 완료 | 2+종 동시탐지 |
| 에이전트 큐 | enqueue.py | ✅ 완료 | tiktoken 토큰 예산 |
| 점수 검증 | validate_100x.py | ✅ 완료 | --save Supabase 저장 |
| 백테스트 | backtest.py | ⚠️ 부분 | screen_scores 의존 (아래 설명) |

### Phase 5 (Next.js 웹) — 92% 완료

| 페이지 | 상태 | 미완 항목 |
|---|---|---|
| / 대시보드 | ✅ 완료 | — |
| /signals | ✅ 완료 | — |
| /watchlist | ✅ 완료 | — |
| /queue | ✅ 완료 | — |
| /stocks/[ticker] | ✅ 완료 | 주가 차트 미구현 |
| /settings | ⚠️ 부분 | 4개 섹션 "준비 중" |
| /backtest | ✅ 완료 | 오늘 신규 구현 |

### Phase 6 (알림 & 스케줄러) — 70% 완료

| 항목 | 상태 | 비고 |
|---|---|---|
| Telegram notify.ts | ⚠️ 미연결 | 함수 구현됨, 실제 호출 없음 |
| Daily workflow | ✅ 완료 | |
| Hourly workflow | ✅ 완료 | |
| Weekly workflow | ⚠️ 부분 | financials_sec 누락 |
| Backtest workflow | ✅ 완료 | validate-backtest.yml |
| pipeline_runs 기록 | ✅ 완료 | |
| 데이터 pruning | ✅ 완료 | prune_prices.py |

---

## 2. 발견된 버그 (심각도 순)

### 🔴 버그 #1: score.py — revenue_2y_ago 항상 None

**파일**: `apps/collector/src/screening/score.py`, 85번째 줄

```python
data["revenue_2y_ago"] = None  # ← 하드코딩된 None
```

**영향**: f04 (성장 가속도) 필터가 프로덕션 스코어링에서 절대 발화하지 않는다.
성장(Growth) 카테고리의 최대 기여분인 `f04` 점수가 항상 0점.
백테스트 대상 종목 중 에코프로·엘앤에프 같은 성장 가속 패턴이 점수에 반영 안 됨.

**수정**: fins[4:8] 구간의 revenue 합계를 revenue_2y_ago로 사용.

```python
# 수정 후
data["revenue_ttm"]    = sum(f.get("revenue", 0) or 0 for f in fins[:4])  or None
data["revenue_prev"]   = sum(f.get("revenue", 0) or 0 for f in fins[4:8]) or None
data["revenue_2y_ago"] = sum(f.get("revenue", 0) or 0 for f in fins[8:12]) or None  # ← 추가
```

**영향받는 테스트**: test_score.py 재실행 필요.

---

### 🔴 버그 #2: score.py — safety 카테고리 항상 10점

**파일**: `apps/collector/src/screening/score.py`, 133번째 줄

```python
safety = 10 - (10 if scores.get("debt_penalty") else 0)
```

`debt_penalty` 키는 filters_kr.py 어디에도 존재하지 않는다.
결과: safety는 항상 10점 → 부채비율이 높은 리스크 종목도 safety 10점.

**수정**: filters_kr.py에서 debt_ratio 직접 파싱.

```python
# score.py _categorize_score 수정 후
stock_data = getattr(filter_result, '_stock_data', {})
debt_r = stock_data.get("debt_ratio")
if debt_r is None:
    safety_raw = 7.5  # unknown → neutral
elif debt_r <= 100:
    safety_raw = 10.0
elif debt_r <= 200:
    safety_raw = 5.0
else:
    safety_raw = 0.0
```

더 간단한 방법: `FilterResult`에 `stock_data` 레퍼런스를 추가하거나,
`scores_by_filter["debt_ratio"]`에 실제 값을 저장하도록 filters_kr.py 수정.

---

### 🔴 버그 #3: score.py — size 카테고리 항상 5점

**파일**: `apps/collector/src/screening/score.py`, 134번째 줄

```python
size = scores.get("f01", 0) + scores.get("us01", 0)  # → 항상 0
return {..., "size": min(100, size + 5)}  # → 항상 5
```

filters_kr.py에서 f01은 pass/fail mandatory 필터이며 `scores_by_filter`에 저장되지 않는다.
결과: size 카테고리가 항상 5점(상수)으로 유니버스 내 상대적 크기를 전혀 반영 못함.

**수정**: market_cap을 기준으로 점수화.

```python
mc = stock_data.get("market_cap")
if mc is None:
    size_raw = 5.0
elif mc >= 10_000_000_000_000:  # 10조+ → 10점
    size_raw = 10.0
elif mc >= 1_000_000_000_000:   # 1조+ → 7점
    size_raw = 7.0
elif mc >= 300_000_000_000:     # 3000억+ → 4점
    size_raw = 4.0
else:
    size_raw = 2.0
```

---

### 🟡 버그 #4: score.py — quality에 f05_margin_trend 누락

**파일**: `apps/collector/src/screening/score.py`, 130번째 줄

```python
quality = scores.get("f05_op_margin", 0) + scores.get("f06_roic", 0) + scores.get("f07_fcf", 0)
# f05_margin_trend 누락!
```

`filters_kr.py`에서 `f05_margin_trend` (영업이익률 개선 추세)가 계산되지만 score.py quality 계산에서 빠짐.

**수정**: `+ scores.get("f05_margin_trend", 0)` 추가.

---

### 🟡 버그 #5: backtest.py — screen_scores 의존으로 역사적 검증 불가

**파일**: `apps/collector/src/screening/backtest.py`

```python
res = client.table("screen_scores").select(...).eq("run_date", target_date).execute()
```

2020-01-01 데이터는 시스템 실행 이전이므로 screen_scores에 없다.
즉 `run_backtest("2020-01-01")`를 호출해도 데이터가 없어 screened=0, hit_rate=0%.
backtest.py는 실질적으로 미래에만 동작하는 구조.

validate_100x.py가 실제 point-in-time 검증 역할을 대체한다.
backtest.py의 의도대로 사용하려면 FDR + DART로 직접 계산해야 함.

**수정 방향**: backtest.py를 validate_100x.py 방식으로 재구현하거나
"현재 스코어 중 향후 3년 10배 달성률"로 목적을 변경.

---

## 3. 백테스트 알고리즘 분석

### 3-1. 주요 발견사항 (이전 세션 결과)

DART API 없이 가격/모멘텀만으로 실행한 결과:

| 구분 | 종목 | RS점수 | 필터결과 | 실제 수익 |
|---|---|---|---|---|
| ★타겟 | 에코프로 | 34 | **f02 탈락** (거래대금 < 5B) | 83.1x |
| ★타겟 | 한미반도체 | 100 | 통과 | 19.7x |
| ★타겟 | 알테오젠 | — | — | 50x |
| ★타겟 | 효성중공업 | — | — | 18x |
| 대조 | LG이노텍 | — | — | 2.5x |
| 대조 | 삼성전기 | — | — | 1.8x |

- 탐지율: 3/6 (50%) — DART 없이는 50% 탐지
- 평균 점수: 타겟 ~2.0점 vs 대조군 ~2.3점 → **사실상 구별 불가**

### 3-2. 핵심 문제: 알고리즘의 근본적 긴장

우리 알고리즘은 현재 **모멘텀 플레이** 포착에 최적화되어 있다:
- f02: 5B KRW 일 거래대금 (이미 시장이 주목한 종목)
- f11: RS >= 70 (이미 상대적 강세인 종목)
- f12: 52주 고점 내 20% (이미 상승 중인 종목)

반면 **진짜 조기 발굴**은 이와 반대다:
- 거래대금 낮음 (시장이 아직 모름)
- RS 낮거나 중간 (아직 모멘텀 없음)
- 52주 고점과 멀리 있음 (아직 상승 안 함)
- **대신**: 실적 가속, 수주 급증, 외국인 매수 시작

에코프로 2020-01-02:
- 시총 수천억 원, 거래대금 수십억 → f02 탈락
- RS 34 → f11 점수 0
- 하지만 EV 배터리 시장 초기 수혜자

**결론**: f02 임계값 5B는 조기 발굴과 직접 충돌한다.

### 3-3. 카테고리별 스코어링 문제

현재 카테고리 점수 최대값 분석:

| 카테고리 | 가중치 | 실제 최대 기여 | 버그 여부 |
|---|---|---|---|
| Growth | 28% | f03(10) + f04(10) = 20 | f04 항상 0 (#1) |
| Momentum | 22% | f11(6) + f12(5) = 11 | 정상 |
| Quality | 18% | f05(8) + f05t(5) + f06(8) + f07(5) = 26 | f05_margin_trend 누락 (#4) |
| Sponsorship | 12% | f10(4) = 4 | 매우 낮음 |
| Value | 8% | 0 (KR 필터 없음) | KR에 value 필터 없음 |
| Safety | 7% | 항상 10 | debt_penalty 버그 (#2) |
| Size | 5% | 항상 5 | f01 누락 (#3) |

**현재 최고 점수 가능치 (버그 수정 전)**:
- Growth: 10 × 28% = 2.8
- Momentum: 11 × 22% = 2.42
- Quality: 21 × 18% = 3.78 (f05t 누락)
- Sponsorship: 4 × 12% = 0.48
- Value: 0
- Safety: 10 × 7% = 0.70
- Size: 5 × 5% = 0.25
- **이론적 최대: 10.43점 / 100**

**버그 수정 후 최고 점수 가능치**:
- Growth: 20 × 28% = 5.6
- Momentum: 11 × 22% = 2.42
- Quality: 26 × 18% = 4.68
- Sponsorship: 4 × 12% = 0.48
- Value: 0
- Safety: 10 × 7% = 0.70
- Size: 10 × 5% = 0.50
- **이론적 최대: 14.38점 / 100**

→ 현재 max 점수가 14점 수준임. 설계상 100점 만점이지만 각 카테고리 raw 점수가 max 10~26이라
가중합이 14점 수준에 머뭄. 이는 각 filter score를 0~100으로 정규화해야 한다.

---

## 4. 개선 계획

### Sprint A — 스코어링 버그 수정 (즉시, 1~2일)

> 효과: 백테스트 점수 신뢰도 대폭 상승, 타겟/대조군 구별력 확보

**A-1. score.py revenue_2y_ago 수정**

```python
# apps/collector/src/screening/score.py, _bulk_fetch_stock_data()
data["revenue_ttm"]    = sum(f.get("revenue",0) or 0 for f in fins[:4])  or None
data["revenue_prev"]   = sum(f.get("revenue",0) or 0 for f in fins[4:8]) or None
data["revenue_2y_ago"] = sum(f.get("revenue",0) or 0 for f in fins[8:12]) or None
```

조건: financials_dart.py가 3년치 데이터를 수집하므로 fins[8:12]까지 존재 가능.

**A-2. score.py 카테고리 정규화 수정**

각 카테고리 raw 점수를 0~100 범위로 정규화:

```python
# _categorize_score() 수정
CATEGORY_MAX = {
    "growth":      20.0,   # f03(10) + f04(10)
    "momentum":    11.0,   # f11(6) + f12(5)
    "quality":     26.0,   # f05(8+5) + f06(8) + f07(5)
    "sponsorship": 4.0,    # f10(4)
    "value":       10.0,   # us15(10) → KR은 PBR 기반 추가 필요
    "safety":      10.0,   # 부채비율 기반
    "size":        10.0,   # 시총 기반
}

def normalize(val, max_val):
    return min(100.0, val / max_val * 100) if max_val > 0 else 0.0
```

**A-3. FilterResult에 stock_data 저장**

safety/size 카테고리 계산을 위해 원본 데이터 접근이 필요:

```python
# filters_kr.py
@dataclass
class FilterResult:
    ticker: str
    passed: bool
    score: float = 0.0
    failed_filters: list[str] = field(default_factory=list)
    scores_by_filter: dict[str, float] = field(default_factory=dict)
    _stock_data: dict = field(default_factory=dict, repr=False)  # ← 추가
```

**A-4. f05_margin_trend quality에 추가**

```python
quality = (scores.get("f05_op_margin", 0)
           + scores.get("f05_margin_trend", 0)  # ← 추가
           + scores.get("f06_roic", 0)
           + scores.get("f07_fcf", 0)
           + scores.get("us05_op_margin", 0)
           + scores.get("us06_roic", 0))
```

**A-5. safety/size 카테고리 실질화**

debt_ratio, market_cap 기반 실질 점수로 교체.

---

### Sprint B — f02 임계값 개선 (중기, 2~3일)

> 효과: 조기 발굴 능력 향상, 에코프로급 초기 단계 포착

현재 f02 고정 임계값 5B KRW는 소형 고성장주를 원천 차단.

**B-1. 시총 연동 임계값**

```python
# filters_kr.py, f02 로직 수정
mc = stock_data.get("market_cap")
if mc is not None and mc < 1_000_000_000_000:  # 시총 1조 미만
    min_daily_value = 1_000_000_000  # 10억 (소형주 기준)
elif mc is not None and mc < 5_000_000_000_000:  # 5조 미만
    min_daily_value = 3_000_000_000  # 30억
else:
    min_daily_value = cfg["kr_min_daily_value"]  # 기본 50억
```

이 방식으로 에코프로(2020년 시총 ~2000억) 같은 소형 고성장주도 통과 가능.

**B-2. 성장률 점수 가중치 증가**

DART 재무 데이터 있을 때 매출성장 > 30% 종목에 추가 보너스:

```python
# filters_kr.py f03 스코어링
if rev_growth is not None and rev_growth >= cfg["kr_min_revenue_growth"]:
    s = min(15, (rev_growth - cfg["kr_min_revenue_growth"]) / 4)  # 기존 /5 → /4, max 10 → 15
    score += s
    result.scores_by_filter["f03"] = s
```

---

### Sprint C — 추가 신호 구현 (중기, 3~5일)

> 효과: 한국 산업재 특화 신호 포착력 향상

**C-1. 수주잔고 점수화**

현재 f08은 pass/fail only. 수주잔고 성장률을 성장 카테고리에 반영:

```python
# filters_kr.py, 스코어링 섹션 추가
backlog = stock_data.get("order_backlog")
backlog_prev = stock_data.get("order_backlog_prev")
if backlog is not None and backlog_prev is not None and backlog_prev > 0:
    backlog_growth = (backlog - backlog_prev) / backlog_prev * 100
    if backlog_growth > 20:
        s = min(10, backlog_growth / 10)
        score += s
        result.scores_by_filter["f08_backlog_growth"] = s
```

**C-2. 외국인 매수 방향성 점수**

현재 외국인 지분율 >= 10% 단순 체크. 방향성(증가 추세)도 반영:

```python
fown_prev = stock_data.get("foreign_ownership_pct_prev")
if fown is not None and fown_prev is not None and fown > fown_prev:
    s = min(4, (fown - fown_prev) * 2)
    score += s
    result.scores_by_filter["f10_foreign_trend"] = s
```

---

### Sprint D — 미완성 UI 완료 (중기, 3~5일)

**D-1. /stocks/[ticker] 주가 차트**

현재 주가 차트가 없고 재무 테이블만 있음.
API가 252일치 가격 데이터를 반환하므로 Recharts LineChart로 시각화:

```tsx
// stocks/[ticker]/page.tsx — Overview 탭에 추가
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts'

<ResponsiveContainer width="100%" height={200}>
  <LineChart data={priceHistory}>
    <XAxis dataKey="date" tick={{ fontSize: 11 }} tickFormatter={d => d.slice(5)} />
    <YAxis domain={['auto', 'auto']} tick={{ fontSize: 11 }} />
    <Tooltip formatter={(v: number) => v.toLocaleString('ko-KR') + '원'} />
    <Line type="monotone" dataKey="close" dot={false} stroke="var(--color-accent)" />
  </LineChart>
</ResponsiveContainer>
```

**D-2. /settings 미완성 4개 섹션**

| 섹션 | 구현 내용 |
|---|---|
| 스케줄 설정 | cron 표현식 표시(편집X), 다음 실행 시각 계산 표시 |
| 알림 채널 | Telegram Chat ID 입력, 알림 조건 토글 (SUPABASE settings 저장) |
| 유니버스 관리 | 수동 티커 추가/제외 (stocks.is_active 토글) |
| 실패 사례 학습 | failure_cases CRUD — 에코프로/헬릭스미스 교훈 기록 |

**D-3. Telegram 알림 연결**

notify.ts의 4개 함수를 실제 이벤트에 연결:

| 이벤트 | 연결 위치 | 함수 |
|---|---|---|
| 골든 시그널 탐지 | golden_signal.py → Supabase Edge Function or Python | notifyGoldenSignal |
| 워치리스트 상태 변경 | /api/watchlist/[id]/route.ts | notifyWatchlistPromotion |
| 파이프라인 연속 실패 | collect-daily.yml 후처리 step | alertPipelineFailure |

가장 빠른 방법: golden_signal.py에서 직접 Telegram API 호출 (Python requests):

```python
# golden_signal.py에 추가
def _notify_golden(ticker: str, summary: str) -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        return
    msg = f"*골든 시그널* [{ticker}]\n{summary}"
    requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                  json={"chat_id": chat_id, "text": msg, "parse_mode": "Markdown"})
```

---

### Sprint E — backtest.py 재설계 (장기, 5~7일)

현재 backtest.py는 `screen_scores` 테이블에 데이터가 있어야만 동작하므로
시스템 가동 이전 기간(2020-2024)에는 사용 불가.

**E-1. validate_100x.py 방식으로 backtest.py 재구현**

```
backtest.py 새 동작 방식:
1. 사용자가 날짜 범위 지정 (예: 2020-01-01 ~ 2020-12-31, 분기별)
2. 각 분기 시작일에 전체 KR 유니버스 대상으로 FDR + DART로 실시간 계산
3. 통과 종목 목록 저장
4. 3년 후 가격으로 10배 달성률 계산
5. 결과 backtest_runs 테이블에 저장
```

이를 통해 "2020년 1월 기준 스크리닝 → 2023년 실제 10배 달성률" 같은
실질적인 알고리즘 검증이 가능.

---

### Sprint F — 미국 주식 스코어링 완성 (장기)

| 항목 | 현재 상태 | 목표 |
|---|---|---|
| 미국 재무 수집 | financials_sec.py 구현됨 | weekly 워크플로우에 추가 |
| 미국 스코어 | filters_us.py 완료 | 백테스트 대상 추가 |
| Value 카테고리 | KR에 없음 | PBR/PER 기반 필터 추가 |
| 미국 수주 신호 | 없음 | 8-K "Purchase Agreement" 금액 파싱 |

---

## 5. 우선순위 매트릭스

| 우선순위 | 작업 | 영향도 | 난이도 | 예상 시간 |
|---|---|---|---|---|
| P0 | Sprint A-1: revenue_2y_ago 수정 | 🔴 높음 | 쉬움 | 30분 |
| P0 | Sprint A-4: f05_margin_trend 추가 | 🔴 높음 | 쉬움 | 10분 |
| P0 | Sprint A-2: 카테고리 정규화 | 🔴 높음 | 중간 | 2시간 |
| P0 | Sprint A-5: safety/size 실질화 | 🔴 높음 | 중간 | 1시간 |
| P1 | Sprint B-1: f02 시총 연동 임계값 | 🟠 중요 | 쉬움 | 1시간 |
| P1 | Sprint D-1: 주가 차트 | 🟡 중간 | 중간 | 3시간 |
| P1 | Sprint D-3: Telegram 연결 | 🟡 중간 | 쉬움 | 2시간 |
| P2 | Sprint C-1: 수주잔고 점수화 | 🟠 중요 | 중간 | 3시간 |
| P2 | Sprint D-2: settings 4개 섹션 | 🟡 중간 | 중간 | 1일 |
| P3 | Sprint E: backtest.py 재설계 | 🟡 중간 | 어려움 | 3~5일 |
| P3 | Sprint F: 미국 주식 완성 | 🟡 중간 | 중간 | 2~3일 |
| P3 | weekly workflow financials_sec | 🟡 낮음 | 쉬움 | 30분 |

---

## 6. 백테스트 재실행 후 예상 결과

버그 수정(Sprint A) 완료 후 DART API 키 설정 상태에서 백테스트 재실행 시 예상:

| 종목 | 현재 예상 | 수정 후 예상 | 변화 요인 |
|---|---|---|---|
| 에코프로 (2020) | ~2점, f02 탈락 | ~8점, 통과 가능 | f02 완화(B-1), f03/f04 DART 반영 |
| 에코프로비엠 (2020) | ~2점 | ~7점 | f03/f04 성장 가속 반영 |
| 엘앤에프 (2020) | ~2점 | ~6점 | f03 성장 반영 |
| 한미반도체 (2021) | ~5점 | ~12점 | f03/f04 + f05 + RS 100 |
| 알테오젠 (2020) | ~3점 | ~9점 | f03 고성장, f07 FCF |
| 효성중공업 (2022) | ~5점 | ~14점 | f03 + f08 수주잔고 + f05 |
| LG이노텍 (대조) | ~3점 | ~5점 | 소폭 상승 |
| 삼성전기 (대조) | ~2점 | ~4점 | 소폭 상승 |
| SK하이닉스 (대조) | ~3점 | ~6점 | 규모 반영 |

목표 탐지율: 버그 수정 후 6/6 (100%), 대조군 통과율 1/3 이하

---

## 7. 다음 즉시 실행 항목

```bash
# 1. Sprint A 버그 수정 (P0)
# - score.py: revenue_2y_ago, 카테고리 정규화, safety, size, f05_margin_trend
# - filters_kr.py: FilterResult에 _stock_data 추가

# 2. 테스트 재실행
cd apps/collector && uv run python -m pytest -q

# 3. Supabase 마이그레이션 실행 (002_backtest.sql)
npx supabase db push

# 4. DART API 키 설정 후 백테스트 재실행
uv run python -m src.screening.validate_100x --save

# 5. f02 임계값 완화 (Sprint B-1)
```
