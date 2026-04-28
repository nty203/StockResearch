'use client'
export const runtime = 'edge'

import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { RiseCategoryBadge, RISE_CATEGORY_META } from '@/components/ui/rise-category-badge'
import type { RiseCategory } from '@stock/shared'

interface BacktestRun {
  id: string
  run_date: string
  dart_used: boolean
  triggered_by: string | null
  created_at: string
}

interface BacktestResult {
  id: string
  run_id: string
  ticker: string
  name: string | null
  market: string | null
  snapshot_date: string
  peak_date: string | null
  actual_x: number | null
  score_10x: number | null
  passed: boolean
  failed_filters: string[] | null
  cats: {
    growth?: number
    momentum?: number
    quality?: number
    sponsorship?: number
    value?: number
    safety?: number
    size?: number
  } | null
  price_at_snapshot: number | null
  rs_score: number | null
  is_target: boolean
}

interface BacktestData {
  runs: BacktestRun[]
  results: BacktestResult[]
}

const CAT_LABELS: Record<string, string> = {
  growth: '성장',
  momentum: '모멘텀',
  quality: '품질',
  sponsorship: '수급',
  value: '가치',
  safety: '안전',
  size: '규모',
}

const CAT_WEIGHTS: Record<string, number> = {
  growth: 28, momentum: 22, quality: 18, sponsorship: 12,
  value: 8, safety: 7, size: 5,
}

// ── 연구 레퍼런스 데이터 (항상 표시, DB 불필요) ──────────────────────────────
interface RefStock {
  ticker: string
  name: string
  market: string
  snapshot: string
  actual_x: number
  rise_categories: RiseCategory[]
  key_signals: string[]
  lead_months: string  // 선행 기간
}

const REFERENCE_STOCKS: RefStock[] = [
  {
    ticker: '086520', name: '에코프로', market: 'KOSDAQ', snapshot: '2020-01', actual_x: 107,
    rise_categories: ['공급_병목'],
    key_signals: ['EV 배터리 공급 부족 기사 급증', '양극재 생산능력 증설 공시', '완성차 CAPEX 폭증'],
    lead_months: '24개월',
  },
  {
    ticker: '042700', name: '한미반도체', market: 'KOSDAQ', snapshot: '2021-01', actual_x: 19,
    rise_categories: ['플랫폼_독점', '빅테크_파트너'],
    key_signals: ['TC본더 글로벌 유일 공급사 지위', 'NVIDIA HBM 생산라인 수주', '고객 CAPEX 증설 연동'],
    lead_months: '12개월',
  },
  {
    ticker: '196170', name: '알테오젠', market: 'KOSDAQ', snapshot: '2020-01', actual_x: 50,
    rise_categories: ['임상_파이프라인'],
    key_signals: ['SC 플랫폼 글로벌 빅파마 기술이전 계약', '히알루로니다제 FDA IND 승인', '마일스톤 수취 공시'],
    lead_months: '18개월',
  },
  {
    ticker: '298040', name: '효성중공업', market: 'KOSPI', snapshot: '2022-01', actual_x: 18,
    rise_categories: ['수주잔고_선행', '수익성_급전환'],
    key_signals: ['미국 전력망 GIS 수주 폭발', '수주잔고/매출 BCR > 1.5x', 'OPM 2%→8% 급반등'],
    lead_months: '9개월',
  },
  {
    ticker: '012450', name: '한화에어로스페이스', market: 'KOSPI', snapshot: '2021-06', actual_x: 20,
    rise_categories: ['수주잔고_선행', '정책_수혜'],
    key_signals: ['폴란드 K-9 자주포 수출 계약(9조원)', 'NATO 재무장 예산 확대', '수주잔고 5배 급증'],
    lead_months: '12개월',
  },
  {
    ticker: '267260', name: 'HD현대일렉트릭', market: 'KOSPI', snapshot: '2022-06', actual_x: 8,
    rise_categories: ['수주잔고_선행', '정책_수혜'],
    key_signals: ['HVDC 변압기 수주 급증', 'IRA 이후 미국 전력망 투자 2배', 'OPM 1%→9% 반등'],
    lead_months: '9개월',
  },
  {
    ticker: '108490', name: '로보티즈', market: 'KOSDAQ', snapshot: '2023-01', actual_x: 12,
    rise_categories: ['플랫폼_독점', '빅테크_파트너'],
    key_signals: ['LG전자 전략적 지분투자(90억)', 'Dynamixel 학술 논문 인용 급증', '오픈AI·구글 휴머노이드 Dynamixel 채택'],
    lead_months: '18개월',
  },
  {
    ticker: '010170', name: '대한광통신', market: 'KOSPI', snapshot: '2025-01', actual_x: 35,
    rise_categories: ['플랫폼_독점', '공급_병목'],
    key_signals: ['국내 유일 모재→광섬유→광케이블 수직계열화', 'AI DC 864심 광케이블 개발 완료', '빅테크 AI DC 광통신 수요 폭발'],
    lead_months: '24개월',
  },
  {
    ticker: '000250', name: '삼천당제약', market: 'KOSPI', snapshot: '2024-06', actual_x: 4.5,
    rise_categories: ['임상_파이프라인'],
    key_signals: ['S-PASS 경구형 GLP-1 일본 기술이전 계약', '유럽 11개국 라이선스(5.3조)', '세마글루타이드 특허 만료 2026년'],
    lead_months: '18개월',
  },
  {
    ticker: '277810', name: '레인보우로보틱스', market: 'KOSDAQ', snapshot: '2022-12', actual_x: 20,
    rise_categories: ['빅테크_파트너'],
    key_signals: ['삼성전자 590억 유상증자 + 콜옵션 조항', '이재용 방문 → 투자 결정', '콜옵션 행사 → 삼성 최대주주(35%)'],
    lead_months: '0일 (공시 당일)',
  },
  {
    ticker: '087010', name: '펩트론', market: 'KOSDAQ', snapshot: '2023-06', actual_x: 41,
    rise_categories: ['임상_파이프라인'],
    key_signals: ['SmartDepo 플랫폼 FDA IND 승인', 'LG화학 루프원 유통 계약', '청주 신공장 착공 (CDMO 생산능력 확대)'],
    lead_months: '18개월',
  },
  {
    ticker: '032820', name: '우리기술', market: 'KOSDAQ', snapshot: '2022-06', actual_x: 13,
    rise_categories: ['정책_수혜', '수주잔고_선행'],
    key_signals: ['탈원전→원전 정책 전환', '체코 두코바니 원전 입찰 참가 공시', 'MMIS 수주잔고/매출 3배 초과'],
    lead_months: '12개월',
  },
]

// 카테고리별 그룹핑
const CATEGORY_GROUPS = Object.keys(RISE_CATEGORY_META) as RiseCategory[]

function ScoreBar({ value, max = 100 }: { value: number; max?: number }) {
  const pct = Math.min(100, (value / max) * 100)
  const color =
    pct >= 60
      ? 'bg-[var(--color-success)]'
      : pct >= 30
      ? 'bg-[var(--color-warning)]'
      : 'bg-[var(--color-error)]'
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 rounded-full bg-[var(--color-border)]">
        <div className={`h-1.5 rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs text-[var(--color-text-2)] w-8 text-right">{value.toFixed(0)}</span>
    </div>
  )
}

function ResultRow({ r }: { r: BacktestResult }) {
  const [expanded, setExpanded] = useState(false)
  const score = r.score_10x ?? 0
  const actualX = r.actual_x ?? 0
  const missed = r.is_target && !r.passed
  const caught = r.is_target && r.passed

  const rowColor = missed
    ? 'border-l-2 border-l-[var(--color-error)]'
    : caught
    ? 'border-l-2 border-l-[var(--color-success)]'
    : 'border-l-2 border-l-[var(--color-border)]'

  return (
    <>
      <tr
        className={`border-b border-[var(--color-border)] cursor-pointer hover:bg-[var(--color-card)] ${rowColor}`}
        onClick={() => setExpanded(!expanded)}
      >
        <td className="px-4 py-2.5">
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium text-[var(--color-text-1)]">{r.ticker}</span>
            {r.name && <span className="text-xs text-[var(--color-text-2)]">{r.name}</span>}
            {r.is_target && (
              <span className="text-xs px-1.5 py-0.5 rounded bg-[var(--color-gold)]/20 text-[var(--color-gold)]">
                타겟
              </span>
            )}
          </div>
          <div className="text-xs text-[var(--color-text-2)] mt-0.5">
            {r.snapshot_date} 시점
            {r.price_at_snapshot && (
              <span className="ml-2">{r.price_at_snapshot.toLocaleString('ko-KR')}원</span>
            )}
          </div>
        </td>
        <td className="px-4 py-2.5 text-right">
          <span
            className={`text-lg font-bold ${
              score >= 20
                ? 'text-[var(--color-success)]'
                : score >= 10
                ? 'text-[var(--color-warning)]'
                : 'text-[var(--color-text-2)]'
            }`}
          >
            {score.toFixed(1)}
          </span>
          <span className="text-xs text-[var(--color-text-2)]">/100</span>
        </td>
        <td className="px-4 py-2.5 text-center">
          {r.passed ? (
            <span className="text-xs px-2 py-1 rounded bg-[var(--color-success)]/20 text-[var(--color-success)]">
              통과
            </span>
          ) : (
            <span className="text-xs px-2 py-1 rounded bg-[var(--color-error)]/20 text-[var(--color-error)]">
              탈락
            </span>
          )}
        </td>
        <td className="px-4 py-2.5 text-right">
          <span
            className={`text-sm font-semibold ${
              actualX >= 10 ? 'text-[var(--color-gold)]' : 'text-[var(--color-text-1)]'
            }`}
          >
            {actualX ? `${actualX.toFixed(1)}x` : '—'}
          </span>
        </td>
        <td className="px-4 py-2.5 text-right text-xs text-[var(--color-text-2)]">
          {r.rs_score != null ? r.rs_score.toFixed(0) : '—'}
        </td>
        <td className="px-4 py-2.5 text-xs text-[var(--color-text-2)]">
          {expanded ? '▲' : '▼'}
        </td>
      </tr>

      {expanded && (
        <tr className="bg-[var(--color-card)] border-b border-[var(--color-border)]">
          <td colSpan={6} className="px-4 py-3">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 sm:gap-6">
              <div>
                <p className="text-xs font-medium text-[var(--color-text-2)] mb-2">카테고리별 점수</p>
                <div className="space-y-1.5">
                  {Object.entries(CAT_LABELS).map(([key, label]) => {
                    const val = r.cats?.[key as keyof typeof r.cats] ?? 0
                    const w = CAT_WEIGHTS[key] ?? 0
                    return (
                      <div key={key} className="flex items-center gap-2">
                        <span className="text-xs text-[var(--color-text-2)] w-20 shrink-0">
                          {label} ({w}%)
                        </span>
                        <div className="flex-1">
                          <ScoreBar value={val} />
                        </div>
                      </div>
                    )
                  })}
                </div>
              </div>
              <div>
                <p className="text-xs font-medium text-[var(--color-text-2)] mb-2">상세 정보</p>
                <div className="space-y-1 text-xs text-[var(--color-text-2)]">
                  <div>
                    시장: <span className="text-[var(--color-text-1)]">{r.market ?? '—'}</span>
                  </div>
                  <div>
                    스냅샷:{' '}
                    <span className="text-[var(--color-text-1)]">{r.snapshot_date}</span>
                  </div>
                  {r.peak_date && (
                    <div>
                      고점: <span className="text-[var(--color-text-1)]">{r.peak_date}</span>
                    </div>
                  )}
                  {r.actual_x && (
                    <div>
                      실제 상승:{' '}
                      <span className="text-[var(--color-gold)] font-semibold">
                        {r.actual_x.toFixed(1)}배
                      </span>
                    </div>
                  )}
                  {r.failed_filters && r.failed_filters.length > 0 && (
                    <div className="mt-2">
                      <span className="text-[var(--color-error)]">탈락 필터:</span>
                      <div className="flex flex-wrap gap-1 mt-1">
                        {r.failed_filters.map(f => (
                          <span
                            key={f}
                            className="px-1.5 py-0.5 rounded bg-[var(--color-error)]/20 text-[var(--color-error)]"
                          >
                            {f}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </div>
          </td>
        </tr>
      )}
    </>
  )
}

function ReferenceCard({ stock }: { stock: RefStock }) {
  const [expanded, setExpanded] = useState(false)
  return (
    <div
      className="rounded-lg bg-[var(--color-surface)] border border-[var(--color-border)] p-3 cursor-pointer hover:border-[var(--color-accent)]/50 transition-colors"
      onClick={() => setExpanded(v => !v)}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="space-y-1 min-w-0">
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="text-sm font-semibold text-[var(--color-text-1)]">{stock.name}</span>
            <span className="text-xs text-[var(--color-text-2)]">{stock.ticker}</span>
            <span className="text-xs px-1.5 py-0.5 rounded bg-[var(--color-card)] text-[var(--color-text-2)]">
              {stock.market}
            </span>
          </div>
          <div className="flex flex-wrap gap-1">
            {stock.rise_categories.map(cat => (
              <RiseCategoryBadge key={cat} category={cat} />
            ))}
          </div>
        </div>
        <div className="text-right shrink-0">
          <div className="text-lg font-bold text-[var(--color-gold)]">{stock.actual_x}x</div>
          <div className="text-xs text-[var(--color-text-2)]">{stock.snapshot}</div>
        </div>
      </div>

      {expanded && (
        <div className="mt-3 pt-3 border-t border-[var(--color-border)] space-y-2">
          <div>
            <span className="text-xs text-[var(--color-text-2)]">선행 기간: </span>
            <span className="text-xs text-[var(--color-accent)]">{stock.lead_months} 전 감지 가능</span>
          </div>
          <div>
            <p className="text-xs font-medium text-[var(--color-text-2)] mb-1">선행 신호</p>
            <ul className="space-y-0.5">
              {stock.key_signals.map((sig, i) => (
                <li key={i} className="text-xs text-[var(--color-text-2)] flex gap-1.5">
                  <span className="text-[var(--color-accent)] shrink-0 mt-0.5">•</span>
                  {sig}
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}
    </div>
  )
}

export default function BacktestPage() {
  const queryClient = useQueryClient()
  const [running, setRunning] = useState(false)
  const [catFilter, setCatFilter] = useState<RiseCategory | 'ALL'>('ALL')

  const { data, isLoading, error } = useQuery<BacktestData>({
    queryKey: ['backtest'],
    queryFn: () => fetch('/api/backtest').then(r => r.json()),
    staleTime: 60_000,
  })

  const trigger = useMutation({
    mutationFn: () => fetch('/api/backtest', { method: 'POST' }).then(r => r.json()),
    onMutate: () => setRunning(true),
    onSuccess: () => {
      setRunning(false)
      setTimeout(() => queryClient.invalidateQueries({ queryKey: ['backtest'] }), 3000)
    },
    onError: () => setRunning(false),
  })

  const results = data?.results ?? []
  const runs = data?.runs ?? []
  const latestRun = runs[0]
  const targets = results.filter(r => r.is_target)
  const controls = results.filter(r => !r.is_target)

  const targetPass = targets.filter(r => r.passed).length
  const controlPass = controls.filter(r => r.passed).length
  const precision = targetPass + controlPass > 0 ? targetPass / (targetPass + controlPass) : 0

  const avgTargetScore =
    targets.length > 0
      ? targets.reduce((s, r) => s + (r.score_10x ?? 0), 0) / targets.length
      : 0
  const avgControlScore =
    controls.length > 0
      ? controls.reduce((s, r) => s + (r.score_10x ?? 0), 0) / controls.length
      : 0

  // 레퍼런스 필터링
  const filteredRef =
    catFilter === 'ALL'
      ? REFERENCE_STOCKS
      : REFERENCE_STOCKS.filter(s => s.rise_categories.includes(catFilter))

  return (
    <div className="space-y-6">
      {/* 헤더 */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-xl font-semibold text-[var(--color-text-1)]">백테스트</h1>
          <p className="text-sm text-[var(--color-text-2)] mt-1">
            실제 100배+ 상승 종목을 상승 전 시점으로 돌려 알고리즘 탐지 능력 검증
          </p>
        </div>
        <button
          onClick={() => trigger.mutate()}
          disabled={running || trigger.isPending}
          className="px-4 py-2 rounded text-sm font-medium bg-[var(--color-accent)] text-white hover:opacity-80 disabled:opacity-40 transition-opacity"
        >
          {running || trigger.isPending ? '실행 중...' : '백테스트 실행'}
        </button>
      </div>

      {(running || trigger.isPending) && (
        <div className="rounded-lg bg-[var(--color-surface)] border border-[var(--color-accent)] p-3 text-sm text-[var(--color-accent)]">
          GitHub Actions에서 백테스트가 실행 중입니다. 완료 후 새로고침하면 결과가 업데이트됩니다.
        </div>
      )}

      {trigger.isError && (
        <div className="rounded-lg bg-[var(--color-surface)] border border-[var(--color-error)] p-3 text-sm text-[var(--color-error)]">
          실행 실패: GitHub PAT 설정을 확인하세요.
        </div>
      )}

      {/* ── 연구 레퍼런스 라이브러리 (항상 표시) ───────────────────────────── */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-base font-semibold text-[var(--color-text-1)]">
              종목 레퍼런스 라이브러리
            </h2>
            <p className="text-xs text-[var(--color-text-2)] mt-0.5">
              12개 종목 케이스 스터디 — 상승 원인 카테고리별 선행 신호 분석
            </p>
          </div>
          {/* 카테고리 필터 */}
          <div className="flex flex-wrap gap-1.5 justify-end">
            <button
              onClick={() => setCatFilter('ALL')}
              className={`text-xs px-2.5 py-1 rounded border transition-colors ${
                catFilter === 'ALL'
                  ? 'bg-[var(--color-accent)]/20 border-[var(--color-accent)] text-[var(--color-accent)]'
                  : 'border-[var(--color-border)] text-[var(--color-text-2)]'
              }`}
            >
              전체
            </button>
            {CATEGORY_GROUPS.map(cat => {
              const meta = RISE_CATEGORY_META[cat]
              const active = catFilter === cat
              return (
                <button
                  key={cat}
                  onClick={() => setCatFilter(cat)}
                  className={`text-xs px-2.5 py-1 rounded border transition-colors ${
                    active
                      ? `${meta.bg} ${meta.color} border-current`
                      : 'border-[var(--color-border)] text-[var(--color-text-2)]'
                  }`}
                >
                  {meta.label}
                </button>
              )
            })}
          </div>
        </div>

        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
          {filteredRef.map(stock => (
            <ReferenceCard key={stock.ticker} stock={stock} />
          ))}
        </div>

        {/* 카테고리 범례 */}
        <div className="rounded-lg bg-[var(--color-surface)] border border-[var(--color-border)] p-3">
          <p className="text-xs font-medium text-[var(--color-text-1)] mb-2">상승 원인 카테고리 정의</p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-1.5">
            {CATEGORY_GROUPS.map(cat => {
              const meta = RISE_CATEGORY_META[cat]
              return (
                <div key={cat} className="flex items-start gap-2">
                  <span
                    className={`shrink-0 mt-0.5 text-xs px-1.5 py-0.5 rounded font-medium ${meta.color} ${meta.bg}`}
                  >
                    {meta.label}
                  </span>
                  <p className="text-xs text-[var(--color-text-2)]">{meta.desc}</p>
                </div>
              )
            })}
          </div>
        </div>
      </div>

      {/* ── 알고리즘 검증 결과 (백테스트 실행 후 표시) ──────────────────────── */}
      <div>
        <h2 className="text-base font-semibold text-[var(--color-text-1)] mb-3">
          알고리즘 검증 결과
        </h2>

        {isLoading && (
          <div className="space-y-3">
            {Array.from({ length: 3 }).map((_, i) => (
              <div key={i} className="h-16 rounded-lg bg-[var(--color-surface)] animate-pulse" />
            ))}
          </div>
        )}

        {error && (
          <div className="rounded-lg bg-[var(--color-surface)] border border-[var(--color-error)] p-4 text-sm text-[var(--color-error)]">
            데이터를 불러오지 못했습니다.
          </div>
        )}

        {!isLoading && !error && results.length === 0 && (
          <div className="rounded-lg bg-[var(--color-surface)] border border-[var(--color-border)] p-6 text-center space-y-2">
            <p className="text-sm text-[var(--color-text-2)]">아직 백테스트 결과가 없습니다.</p>
            <p className="text-xs text-[var(--color-text-2)]">
              "백테스트 실행" 버튼으로 GitHub Actions 워크플로우를 실행하세요.
            </p>
          </div>
        )}

        {results.length > 0 && (
          <>
            {/* 요약 카드 */}
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-4 mb-4">
              <div className="rounded-lg bg-[var(--color-surface)] border border-[var(--color-border)] p-4">
                <p className="text-xs text-[var(--color-text-2)]">타겟 탐지율</p>
                <p className="text-2xl font-bold text-[var(--color-text-1)] mt-1">
                  {targetPass}/{targets.length}
                </p>
                <p className="text-xs text-[var(--color-text-2)] mt-0.5">
                  {targets.length > 0
                    ? `${((targetPass / targets.length) * 100).toFixed(0)}%`
                    : '—'}
                </p>
              </div>
              <div className="rounded-lg bg-[var(--color-surface)] border border-[var(--color-border)] p-4">
                <p className="text-xs text-[var(--color-text-2)]">정밀도</p>
                <p className="text-2xl font-bold text-[var(--color-text-1)] mt-1">
                  {(precision * 100).toFixed(0)}%
                </p>
                <p className="text-xs text-[var(--color-text-2)] mt-0.5">통과 중 실제 타겟</p>
              </div>
              <div className="rounded-lg bg-[var(--color-surface)] border border-[var(--color-border)] p-4">
                <p className="text-xs text-[var(--color-text-2)]">타겟 평균 점수</p>
                <p className="text-2xl font-bold text-[var(--color-success)] mt-1">
                  {avgTargetScore.toFixed(1)}
                </p>
                <p className="text-xs text-[var(--color-text-2)] mt-0.5">
                  vs 대조군 {avgControlScore.toFixed(1)}
                </p>
              </div>
              <div className="rounded-lg bg-[var(--color-surface)] border border-[var(--color-border)] p-4">
                <p className="text-xs text-[var(--color-text-2)]">마지막 실행</p>
                <p className="text-sm font-medium text-[var(--color-text-1)] mt-1">
                  {latestRun ? new Date(latestRun.created_at).toLocaleDateString('ko-KR') : '—'}
                </p>
                <p className="text-xs text-[var(--color-text-2)] mt-0.5">
                  {latestRun?.dart_used ? 'DART 포함' : 'DART 미포함'}
                </p>
              </div>
            </div>

            {/* 결과 테이블 */}
            <div className="rounded-lg bg-[var(--color-surface)] border border-[var(--color-border)] overflow-hidden">
              <div className="px-4 py-3 border-b border-[var(--color-border)]">
                <p className="text-sm font-medium text-[var(--color-text-1)]">
                  종목별 결과{' '}
                  <span className="text-[var(--color-text-2)] font-normal ml-1">
                    — 행 클릭으로 카테고리 상세 보기
                  </span>
                </p>
                <div className="flex items-center gap-4 mt-1.5 text-xs text-[var(--color-text-2)]">
                  <span className="flex items-center gap-1">
                    <span className="w-2 h-2 rounded-full bg-[var(--color-success)] inline-block" />{' '}
                    타겟 탐지
                  </span>
                  <span className="flex items-center gap-1">
                    <span className="w-2 h-2 rounded-full bg-[var(--color-error)] inline-block" />{' '}
                    타겟 미탐지
                  </span>
                  <span className="flex items-center gap-1">
                    <span className="w-2 h-2 rounded-full bg-[var(--color-border)] inline-block" />{' '}
                    대조군
                  </span>
                </div>
              </div>
              <div className="overflow-x-auto">
              <table className="w-full min-w-[560px]">
                <thead>
                  <tr className="text-xs text-[var(--color-text-2)] border-b border-[var(--color-border)]">
                    <th className="px-4 py-2.5 text-left">종목</th>
                    <th className="px-4 py-2.5 text-right">10X 점수</th>
                    <th className="px-4 py-2.5 text-center">필터</th>
                    <th className="px-4 py-2.5 text-right">실제 수익률</th>
                    <th className="px-4 py-2.5 text-right">RS점수</th>
                    <th className="px-4 py-2.5" />
                  </tr>
                </thead>
                <tbody>
                  {targets.map(r => (
                    <ResultRow key={r.id} r={r} />
                  ))}
                  {targets.length > 0 && controls.length > 0 && (
                    <tr>
                      <td
                        colSpan={6}
                        className="px-4 py-1.5 text-xs text-[var(--color-text-2)] bg-[var(--color-card)]"
                      >
                        대조군 (상승 소폭)
                      </td>
                    </tr>
                  )}
                  {controls.map(r => (
                    <ResultRow key={r.id} r={r} />
                  ))}
                </tbody>
              </table>
              </div>
            </div>

            {runs.length > 1 && (
              <div className="rounded-lg bg-[var(--color-surface)] border border-[var(--color-border)] p-4 mt-4">
                <p className="text-sm font-medium text-[var(--color-text-1)] mb-3">실행 이력</p>
                <div className="space-y-1.5">
                  {runs.map((run, i) => (
                    <div
                      key={run.id}
                      className="flex items-center justify-between text-xs text-[var(--color-text-2)]"
                    >
                      <span>{new Date(run.created_at).toLocaleString('ko-KR')}</span>
                      <span className="flex items-center gap-2">
                        {run.dart_used ? (
                          <span className="text-[var(--color-success)]">DART 포함</span>
                        ) : (
                          <span>DART 미포함</span>
                        )}
                        {i === 0 && (
                          <span className="px-1.5 py-0.5 rounded bg-[var(--color-accent)]/20 text-[var(--color-accent)]">
                            최신
                          </span>
                        )}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}
