'use client'
export const runtime = 'edge'

import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useParams } from 'next/navigation'
import type { ScreenScore, AgentScore, TriggerEvent, Stock } from '@stock/shared'

type Tab = 'overview' | 'events' | 'risk'

interface Financials {
  quarters: { fq: string; revenue: number | null; op_margin: number | null; roic: number | null; fcf: number | null; debt_ratio: number | null; roe: number | null }[]
  revenue_ttm: number | null
  revenue_prev: number | null
  rev_growth_pct: number | null
  op_margin: number | null
  op_margin_prev: number | null
  roic: number | null
  fcf: number | null
  debt_ratio: number | null
  roe: number | null
}

interface PriceContext {
  current: number | null
  high_52w: number | null
  pct_from_high: number | null
  avg_daily_value: number | null
}

interface StockDetail {
  stock: Stock
  score: ScreenScore | null
  agentScores: AgentScore[]
  events: TriggerEvent[]
  financials: Financials
  priceContext: PriceContext
}

const SCORE_CATEGORIES = [
  { key: 'growth',      label: '성장성',   max: 28 },
  { key: 'momentum',    label: '모멘텀',   max: 22 },
  { key: 'quality',     label: '품질',     max: 18 },
  { key: 'sponsorship', label: '수급',     max: 12 },
  { key: 'value',       label: '밸류',     max: 8  },
  { key: 'safety',      label: '안전성',   max: 7  },
  { key: 'size',        label: '규모',     max: 5  },
] as const

const FILTER_LABELS: Record<string, string> = {
  f01_market_cap:      '시가총액 미달',
  f02_daily_value:     '거래대금 미달',
  f03_revenue_growth:  '매출 성장률 미달 (기준: 20% YoY)',
  f08_backlog:         '수주잔고/매출 데이터 없음',
  f09_debt_ratio:      '부채비율 초과 (기준: 200%)',
  us01_market_cap:     '시가총액 미달',
  us02_daily_value:    '거래대금 미달',
  us03_revenue_growth: '매출 성장률 미달',
  us08_backlog:        '수주잔고 데이터 없음',
  us09_debt_ratio:     '부채비율 초과',
}

function fmt(n: number | null, decimals = 1, suffix = '') {
  if (n == null) return '—'
  return n.toFixed(decimals) + suffix
}

function fmtBillion(n: number | null) {
  if (n == null) return '—'
  const abs = Math.abs(n)
  if (abs >= 1e12) return (n / 1e12).toFixed(1) + '조'
  if (abs >= 1e8)  return (n / 1e8).toFixed(0) + '억'
  return n.toFixed(0)
}

// 필터코드 → 한국어 라벨 (Python 스코어링 엔진의 scores_by_filter 키와 1:1 대응)
const FILTER_LABEL: Record<string, string> = {
  f03:               '매출 YoY 성장',
  f04:               '성장 가속',
  f13_bcr:           '수주잔고 확보',
  f14_backlog_growth:'수주 증가',
  us03:              '매출 YoY 성장',
  us04_accel:        '성장 가속',
  f11_rs:            '상대강도 우수',
  f12_momentum:      '고점 근접',
  us11_rs:           '상대강도 우수',
  us12_momentum:     '고점 근접',
  f05_op_margin:     '영업이익률 우수',
  f05_margin_trend:  '이익률 개선',
  f15_opm_inflection:'이익률 전환',
  f06_roic:          'ROIC 우수',
  f07_fcf:           'FCF 양호',
  us05_op_margin:    '영업이익률 우수',
  us06_roic:         'ROIC 우수',
  f10_foreign:       '외국인 지분 확대',
  us10_institutional:'기관 지분 확대',
  us15_ps:           'P/S 밸류 양호',
  safety_score:      '부채비율 건전',
  size_score:        '거래대금 양호',
}

const CATEGORY_FILTERS: Record<string, string[]> = {
  growth:      ['f03', 'f04', 'f13_bcr', 'f14_backlog_growth', 'us03', 'us04_accel'],
  momentum:    ['f11_rs', 'f12_momentum', 'us11_rs', 'us12_momentum'],
  quality:     ['f05_op_margin', 'f05_margin_trend', 'f15_opm_inflection', 'f06_roic', 'f07_fcf', 'us05_op_margin', 'us06_roic'],
  sponsorship: ['f10_foreign', 'us10_institutional'],
  value:       ['us15_ps'],
  safety:      ['safety_score'],
  size:        ['size_score'],
}

function buildCategorySummary(
  cat: string,
  scoresMap: Record<string, number> | null | undefined
): string | null {
  if (!scoresMap) return null
  const filters = CATEGORY_FILTERS[cat] ?? []
  const fired = filters.filter(f => (scoresMap[f] ?? 0) > 0)
  if (fired.length === 0) return null
  return fired.map(f => FILTER_LABEL[f] ?? f).join(' · ')
}

function StatusDot({ ok }: { ok: boolean | null }) {
  if (ok == null) return <span className="text-[var(--color-text-2)] text-xs">—</span>
  return ok
    ? <span className="text-[var(--color-success)] text-xs">✓</span>
    : <span className="text-[var(--color-error)] text-xs">✗</span>
}

function MetricRow({ label, value, ok, sub }: { label: string; value: string; ok?: boolean | null; sub?: string }) {
  return (
    <tr className="border-b border-[var(--color-border)]/50">
      <td className="py-2 pr-4 text-xs text-[var(--color-text-2)] whitespace-nowrap">{label}</td>
      <td className="py-2 pr-3 text-xs font-medium text-[var(--color-text-1)]">{value}</td>
      <td className="py-2 pr-3 w-6">{ok != null ? <StatusDot ok={ok} /> : null}</td>
      <td className="py-2 text-xs text-[var(--color-text-2)]">{sub ?? ''}</td>
    </tr>
  )
}

export default function StockDetailPage() {
  const { ticker } = useParams<{ ticker: string }>()
  const [tab, setTab] = useState<Tab>('overview')

  const { data, isLoading, error } = useQuery<StockDetail>({
    queryKey: ['stock-detail', ticker],
    queryFn: () => fetch(`/api/stocks/${ticker}`).then(r => r.json()),
    staleTime: 5 * 60_000,
  })

  if (isLoading) {
    return (
      <div className="space-y-4">
        <div className="h-24 rounded-lg bg-[var(--color-surface)] animate-pulse" />
        <div className="h-64 rounded-lg bg-[var(--color-surface)] animate-pulse" />
      </div>
    )
  }

  if (error || !data || !data.stock) {
    return (
      <div className="rounded-lg bg-[var(--color-surface)] border border-[var(--color-error)] p-6">
        <p className="text-sm text-[var(--color-error)]">
          {error ? '종목 데이터를 불러오지 못했습니다.' : `종목 ${ticker}을(를) 찾을 수 없습니다.`}
        </p>
      </div>
    )
  }

  const { stock, score, agentScores, events, financials, priceContext } = data
  const failedSet = new Set(score?.failed_filters ?? [])

  return (
    <div className="space-y-6">
      {/* Hero */}
      <div className="rounded-lg bg-[var(--color-surface)] border border-[var(--color-border)] p-6">
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-3 flex-wrap">
              <span className="text-2xl font-bold text-[var(--color-text-1)]">{ticker}</span>
              {(stock.name_kr || stock.name_en) && (
                <span className="text-lg text-[var(--color-text-2)]">{stock.name_kr || stock.name_en}</span>
              )}
              <span className="text-xs px-1.5 py-0.5 rounded bg-[var(--color-card)] text-[var(--color-text-2)]">
                {stock.market}
              </span>
              {score && (
                <span className={`text-xs px-1.5 py-0.5 rounded font-medium ${score.passed ? 'bg-[var(--color-success)]/15 text-[var(--color-success)]' : 'bg-[var(--color-error)]/15 text-[var(--color-error)]'}`}>
                  {score.passed ? '필터 통과' : '필터 미통과'}
                </span>
              )}
            </div>
            {stock.sector_wics && (
              <p className="text-sm text-[var(--color-text-2)] mt-1">{stock.sector_wics}{stock.industry ? ` · ${stock.industry}` : ''}</p>
            )}
            {score && (
              <p className="text-xs text-[var(--color-text-2)] mt-1">
                기준일: {score.run_date}
                {score.percentile > 0 && ` · 상위 ${(100 - score.percentile).toFixed(0)}%`}
                {priceContext.current && ` · 현재가 ${priceContext.current.toLocaleString()}`}
              </p>
            )}
          </div>
          {score && (
            <div className="text-right shrink-0">
              <div className="text-3xl font-bold text-[var(--color-text-1)]">{Math.round(score.score_10x ?? 0)}</div>
              <div className="text-xs text-[var(--color-text-2)]">10X Score</div>
              {score.percentile > 0 && (
                <div className="text-xs text-[var(--color-accent)] mt-0.5">상위 {(100 - score.percentile).toFixed(0)}%</div>
              )}
            </div>
          )}
        </div>
      </div>

      <div className="flex gap-6">
        {/* Main content */}
        <div className="flex-1 min-w-0 space-y-4">
          <div className="flex gap-1 border-b border-[var(--color-border)]">
            {(['overview', 'events', 'risk'] as Tab[]).map(t => (
              <button
                key={t}
                onClick={() => setTab(t)}
                className={`px-4 py-2 text-sm font-medium transition-colors ${
                  tab === t
                    ? 'text-[var(--color-text-1)] border-b-2 border-[var(--color-accent)]'
                    : 'text-[var(--color-text-2)] hover:text-[var(--color-text-1)]'
                }`}
              >
                {t === 'overview' ? '점수 근거' : t === 'events' ? '이벤트' : '리스크'}
              </button>
            ))}
          </div>

          {tab === 'overview' && (
            <div className="space-y-4">
              {/* Failed filters */}
              {score && !score.passed && failedSet.size > 0 && (
                <div className="rounded-lg bg-[var(--color-error)]/8 border border-[var(--color-error)]/30 p-4">
                  <p className="text-xs font-semibold text-[var(--color-error)] mb-2">필수 필터 미통과 — 점수 산정 제외</p>
                  <ul className="space-y-1">
                    {score.failed_filters.map(f => (
                      <li key={f} className="text-xs text-[var(--color-text-2)] flex gap-2">
                        <span className="text-[var(--color-error)]">✗</span>
                        {FILTER_LABELS[f] ?? f}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Financial metrics */}
              <div className="rounded-lg bg-[var(--color-surface)] border border-[var(--color-border)] p-4">
                <p className="text-xs font-semibold text-[var(--color-text-1)] mb-3">재무 지표</p>
                <table className="w-full">
                  <tbody>
                    <MetricRow
                      label="매출 성장률 (YoY)"
                      value={fmt(financials.rev_growth_pct, 1, '%')}
                      ok={financials.rev_growth_pct == null ? null : financials.rev_growth_pct >= 20}
                      sub={financials.revenue_ttm != null ? `TTM ${fmtBillion(financials.revenue_ttm)}` : undefined}
                    />
                    <MetricRow
                      label="영업이익률"
                      value={fmt(financials.op_margin, 1, '%')}
                      ok={financials.op_margin == null ? null : financials.op_margin > 10}
                      sub={financials.op_margin_prev != null
                        ? `전기 ${financials.op_margin_prev.toFixed(1)}% → ${financials.op_margin != null ? (financials.op_margin >= financials.op_margin_prev ? '개선' : '악화') : '—'}`
                        : undefined}
                    />
                    <MetricRow
                      label="ROIC"
                      value={fmt(financials.roic, 1, '%')}
                      ok={financials.roic == null ? null : financials.roic > 15}
                      sub="기준: 15% 초과"
                    />
                    <MetricRow
                      label="FCF"
                      value={fmtBillion(financials.fcf)}
                      ok={financials.fcf == null ? null : financials.fcf > 0}
                      sub={financials.fcf != null ? (financials.fcf > 0 ? '잉여현금흐름 양호' : '현금 소진 중') : undefined}
                    />
                    <MetricRow
                      label="부채비율"
                      value={fmt(financials.debt_ratio, 0, '%')}
                      ok={financials.debt_ratio == null ? null : financials.debt_ratio <= 200}
                      sub="기준: 200% 이하"
                    />
                    <MetricRow
                      label="ROE"
                      value={fmt(financials.roe, 1, '%')}
                      ok={null}
                    />
                  </tbody>
                </table>
              </div>

              {/* Price / momentum */}
              <div className="rounded-lg bg-[var(--color-surface)] border border-[var(--color-border)] p-4">
                <p className="text-xs font-semibold text-[var(--color-text-1)] mb-3">가격·모멘텀</p>
                <table className="w-full">
                  <tbody>
                    <MetricRow
                      label="52주 고가 대비"
                      value={priceContext.pct_from_high != null ? `-${fmt(priceContext.pct_from_high, 1, '%')}` : '—'}
                      ok={priceContext.pct_from_high == null ? null : priceContext.pct_from_high <= 20}
                      sub="기준: 고가 대비 -20% 이내"
                    />
                    <MetricRow
                      label="52주 고가"
                      value={priceContext.high_52w != null ? priceContext.high_52w.toLocaleString() : '—'}
                      ok={null}
                    />
                    <MetricRow
                      label="20일 평균 거래대금"
                      value={fmtBillion(priceContext.avg_daily_value)}
                      ok={priceContext.avg_daily_value == null ? null : priceContext.avg_daily_value >= 5_000_000_000}
                      sub="기준: 50억 이상 (KOSPI)"
                    />
                  </tbody>
                </table>
              </div>

              {/* Quarter history */}
              {financials.quarters.length > 0 && (
                <div className="rounded-lg bg-[var(--color-surface)] border border-[var(--color-border)] p-4">
                  <p className="text-xs font-semibold text-[var(--color-text-1)] mb-3">분기 실적 추이</p>
                  <div className="overflow-x-auto">
                    <table className="w-full text-xs">
                      <thead>
                        <tr className="text-[var(--color-text-2)] border-b border-[var(--color-border)]">
                          <th className="text-left py-1 pr-4 font-medium">분기</th>
                          <th className="text-right py-1 pr-4 font-medium">매출</th>
                          <th className="text-right py-1 pr-4 font-medium">영업이익률</th>
                          <th className="text-right py-1 pr-4 font-medium">ROIC</th>
                          <th className="text-right py-1 font-medium">부채비율</th>
                        </tr>
                      </thead>
                      <tbody>
                        {financials.quarters.map(q => (
                          <tr key={q.fq} className="border-b border-[var(--color-border)]/40">
                            <td className="py-1.5 pr-4 text-[var(--color-text-2)]">{q.fq}</td>
                            <td className="py-1.5 pr-4 text-right text-[var(--color-text-1)]">{fmtBillion(q.revenue)}</td>
                            <td className="py-1.5 pr-4 text-right text-[var(--color-text-1)]">{fmt(q.op_margin, 1, '%')}</td>
                            <td className="py-1.5 pr-4 text-right text-[var(--color-text-1)]">{fmt(q.roic, 1, '%')}</td>
                            <td className="py-1.5 text-right text-[var(--color-text-1)]">{fmt(q.debt_ratio, 0, '%')}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>
          )}

          {tab === 'events' && (
            <div className="space-y-2">
              {events.length === 0 ? (
                <div className="rounded-lg bg-[var(--color-surface)] border border-[var(--color-border)] p-6 text-center">
                  <p className="text-sm text-[var(--color-text-2)]">등록된 트리거 이벤트 없음</p>
                </div>
              ) : (
                events.map(ev => (
                  <div key={ev.id} className="rounded bg-[var(--color-surface)] border border-[var(--color-border)] p-3">
                    <div className="flex items-start gap-3">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="text-xs px-1.5 py-0.5 rounded bg-[var(--color-card)] text-[var(--color-accent)]">
                            {ev.event_type}
                          </span>
                          {ev.golden && (
                            <span className="text-xs px-1.5 py-0.5 rounded bg-[var(--color-gold)]/20 text-[var(--color-gold)]">
                              골든
                            </span>
                          )}
                          <span className="text-xs text-[var(--color-text-2)]">신뢰도 {(ev.confidence * 100).toFixed(0)}%</span>
                        </div>
                        <p className="text-sm text-[var(--color-text-2)] mt-1">{ev.summary}</p>
                        {ev.matched_keywords?.length > 0 && (
                          <div className="flex flex-wrap gap-1 mt-1">
                            {ev.matched_keywords.map(kw => (
                              <span key={kw} className="text-[10px] px-1 py-0.5 rounded bg-[var(--color-card)] text-[var(--color-text-2)]">{kw}</span>
                            ))}
                          </div>
                        )}
                      </div>
                      <span className="text-xs text-[var(--color-text-2)] shrink-0">
                        {new Date(ev.detected_at).toLocaleDateString('ko-KR')}
                      </span>
                    </div>
                  </div>
                ))
              )}
            </div>
          )}

          {tab === 'risk' && (
            <div>
              {agentScores.length === 0 ? (
                <div className="rounded-lg bg-[var(--color-surface)] border border-[var(--color-border)] p-6 text-center space-y-2">
                  <p className="text-sm text-[var(--color-text-2)]">에이전트 분석 결과가 없습니다.</p>
                  <a href="/queue" className="text-xs text-[var(--color-accent)] hover:underline">
                    분석 큐에 추가하기 →
                  </a>
                </div>
              ) : (
                <div className="space-y-3">
                  {agentScores.map((s, i) => (
                    <div key={i} className="rounded-lg bg-[var(--color-surface)] border border-[var(--color-border)] p-4">
                      <div className="text-xs text-[var(--color-text-2)] mb-2">{s.prompt_type}</div>
                      {s.narrative_md && (
                        <p className="text-sm text-[var(--color-text-1)] mb-2 whitespace-pre-wrap">{s.narrative_md}</p>
                      )}
                      {s.risks_md && (
                        <p className="text-sm text-[var(--color-text-2)] whitespace-pre-wrap">{s.risks_md}</p>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Score sidebar */}
        {score && (
          <div className="w-48 shrink-0 sticky top-20 self-start">
            <div className="rounded-lg bg-[var(--color-surface)] border border-[var(--color-border)] p-4 space-y-2">
              {SCORE_CATEGORIES.map(cat => {
                const val = (score as unknown as Record<string, unknown>)[cat.key] as number | null
                const pct = val != null ? Math.min(100, Math.round((val / cat.max) * 100)) : 0
                const summary = buildCategorySummary(cat.key, score.scores_by_filter)
                return (
                  <div key={cat.key}>
                    <div className="flex justify-between text-xs text-[var(--color-text-2)] mb-0.5">
                      <span>{cat.label}</span>
                      <span className="text-[var(--color-text-1)]">{val != null ? val.toFixed(0) : '—'}<span className="text-[var(--color-text-2)] font-normal">/{cat.max}</span></span>
                    </div>
                    <div className="h-1.5 rounded-full bg-[var(--color-card)]">
                      <div
                        className="h-1.5 rounded-full bg-[var(--color-accent)]"
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                    {summary && (
                      <p className="text-[10px] text-[var(--color-text-2)] mt-0.5 leading-snug">{summary}</p>
                    )}
                  </div>
                )
              })}
              <div className="pt-2 border-t border-[var(--color-border)]">
                <div className="flex justify-between text-xs">
                  <span className="text-[var(--color-text-2)]">시장 게이트</span>
                  <span className="text-[var(--color-text-1)]">{score.market_gate === 1 ? '열림' : '0.7배'}</span>
                </div>
              </div>
              {agentScores.length > 0 && (
                <div className="pt-2 border-t border-[var(--color-border)] space-y-1">
                  <div className="flex justify-between text-xs">
                    <span className="text-[var(--color-text-2)]">수요</span>
                    <span className="text-[var(--color-text-1)]">{agentScores[0]?.demand_score ?? '—'}/10</span>
                  </div>
                  <div className="flex justify-between text-xs">
                    <span className="text-[var(--color-text-2)]">해자</span>
                    <span className="text-[var(--color-text-1)]">{agentScores[0]?.moat_score ?? '—'}/10</span>
                  </div>
                  <div className="flex justify-between text-xs">
                    <span className="text-[var(--color-text-2)]">트리거</span>
                    <span className="text-[var(--color-text-1)]">{agentScores[0]?.trigger_score ?? '—'}/10</span>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
