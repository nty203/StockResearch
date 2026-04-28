'use client'
export const runtime = 'edge'

import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useParams } from 'next/navigation'
import type { ScreenScore, AgentScore, TriggerEvent, Stock, RiseCategory } from '@stock/shared'
import { RiseCategoryBadge, RISE_CATEGORY_META } from '@/components/ui/rise-category-badge'

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
  order_backlog: number | null
  order_backlog_prev: number | null
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

// ── 100X 판단 근거 도출 ──────────────────────────────────────────────────────

type FilterEvidence = { label: string; value: string; positive: boolean }

type RiseReason = {
  category: RiseCategory
  headline: string
  evidence: FilterEvidence[]
  why100x: string
  confidence: 'high' | 'medium' | 'low'
  secondaryCategories: RiseCategory[]
}

function deriveRiseReason(
  scoresMap: Record<string, number> | null | undefined,
  financials: Financials,
  priceContext: PriceContext,
  events: TriggerEvent[],
): RiseReason | null {
  if (!scoresMap) return null

  type Candidate = { cat: RiseCategory; score: number; reason: Omit<RiseReason, 'category' | 'secondaryCategories'> }
  const candidates: Candidate[] = []

  // ── 1. 수주잔고_선행 ────────────────────────────────────────────────────────
  const bcrScore = scoresMap['f13_bcr'] ?? 0
  const backlogGrowthScore = scoresMap['f14_backlog_growth'] ?? 0
  if (bcrScore > 0 || backlogGrowthScore > 0) {
    const bcr = bcrScore / 5 // f13_bcr = min(10, BCR*5) → BCR = score/5
    const ev: FilterEvidence[] = []
    if (bcr > 0) {
      const bcrDisplay = financials.order_backlog && financials.revenue_ttm
        ? (financials.order_backlog / financials.revenue_ttm).toFixed(1) + 'x'
        : bcr.toFixed(1) + 'x'
      ev.push({ label: '수주잔고/매출(BCR)', value: bcrDisplay + ' 확보', positive: true })
    }
    if (backlogGrowthScore > 0) {
      const pctApprox = 20 + backlogGrowthScore * 8
      ev.push({ label: '수주잔고 YoY', value: `+${pctApprox.toFixed(0)}%+ 증가`, positive: true })
    }
    if (financials.rev_growth_pct != null)
      ev.push({ label: '매출 성장', value: `${financials.rev_growth_pct.toFixed(0)}% YoY`, positive: financials.rev_growth_pct >= 20 })
    if (financials.order_backlog != null)
      ev.push({ label: '수주잔고 잔액', value: fmtBillion(financials.order_backlog), positive: true })

    candidates.push({
      cat: '수주잔고_선행',
      score: bcrScore * 2.5 + backlogGrowthScore * 2 + (scoresMap['f03'] ?? 0) * 0.5,
      reason: {
        headline: `수주잔고가 매출의 ${bcr > 0 ? bcr.toFixed(1) + 'x' : '확보'}되어 향후 12개월 매출이 선행으로 확정된 구간`,
        evidence: ev,
        why100x: '수주잔고는 매출보다 9~12개월 앞서는 선행지표입니다. 잔고가 쌓이는 구간에서 주가는 실적 인식 전에 반응하며, BCR 2x 이상 + YoY 성장 조합은 멀티플 재평가 트리거가 됩니다.',
        confidence: bcrScore >= 6 ? 'high' : bcrScore >= 3 ? 'medium' : 'low',
      },
    })
  }

  // ── 2. 수익성_급전환 ────────────────────────────────────────────────────────
  const opmInflection = scoresMap['f15_opm_inflection'] ?? 0
  const marginTrend = scoresMap['f05_margin_trend'] ?? 0
  const isLowBase = financials.op_margin_prev != null && financials.op_margin_prev < 10
  if (opmInflection > 0 || (marginTrend > 0 && isLowBase)) {
    const ev: FilterEvidence[] = []
    if (financials.op_margin_prev != null && financials.op_margin != null) {
      ev.push({ label: '영업이익률 전환', value: `${financials.op_margin_prev.toFixed(1)}% → ${financials.op_margin.toFixed(1)}%`, positive: true })
      const improvement = financials.op_margin - financials.op_margin_prev
      ev.push({ label: '이익률 개선폭', value: `+${improvement.toFixed(1)}pp`, positive: true })
    }
    if (financials.roic != null)
      ev.push({ label: 'ROIC', value: `${financials.roic.toFixed(1)}%`, positive: financials.roic > 10 })

    candidates.push({
      cat: '수익성_급전환',
      score: opmInflection * 3 + marginTrend * 1.5,
      reason: {
        headline: `저마진 베이스(${financials.op_margin_prev?.toFixed(1) ?? '?'}%)에서 영업이익률 급등 — 영업레버리지 전환점 포착`,
        evidence: ev,
        why100x: '고정비 구조에서 매출이 임계점을 넘으면 이익이 기하급수적으로 증가합니다. 전환 초입에서 EV/EBIT 멀티플이 적자→흑자로 바뀌는 순간 시장이 재평가하며, 이 구간의 주가 상승폭이 가장 큽니다.',
        confidence: opmInflection >= 5 ? 'high' : 'medium',
      },
    })
  }

  // ── 3. 플랫폼_독점 ──────────────────────────────────────────────────────────
  const roicScore = scoresMap['f06_roic'] ?? 0
  const opMarginScore = scoresMap['f05_op_margin'] ?? 0
  const fcfScore = scoresMap['f07_fcf'] ?? 0
  if (roicScore > 3 && opMarginScore > 3 && bcrScore === 0) {
    const ev: FilterEvidence[] = []
    if (financials.roic != null) ev.push({ label: 'ROIC', value: `${financials.roic.toFixed(1)}%`, positive: financials.roic > 15 })
    if (financials.op_margin != null) ev.push({ label: '영업이익률', value: `${financials.op_margin.toFixed(1)}%`, positive: financials.op_margin > 10 })
    if (fcfScore > 0 && financials.fcf != null) ev.push({ label: 'FCF', value: fmtBillion(financials.fcf), positive: financials.fcf > 0 })

    candidates.push({
      cat: '플랫폼_독점',
      score: roicScore + opMarginScore + fcfScore,
      reason: {
        headline: `ROIC ${financials.roic?.toFixed(0) ?? '?'}%, 고영업마진 — 경쟁자가 진입하기 어려운 플랫폼 해자 구조`,
        evidence: ev,
        why100x: '경제적 해자가 있는 플랫폼은 시장이 확대될수록 이익이 비선형으로 성장합니다. ROIC > 15%는 내부 자본을 복리로 재투자하고 있다는 신호이며, TAM 확대 + 독점 구조는 장기 10배 이상 상승의 핵심 조건입니다.',
        confidence: roicScore >= 5 && opMarginScore >= 5 ? 'high' : 'medium',
      },
    })
  }

  // ── 4. 빅테크_파트너 ────────────────────────────────────────────────────────
  const foreignScore = scoresMap['f10_foreign'] ?? 0
  const institutionalScore = scoresMap['us10_institutional'] ?? 0
  const partnerTriggers = events.filter(e =>
    ['빅테크_파트너', '단일_수주', '기관_집중', '내부자_매수'].includes(e.event_type)
  )
  if (foreignScore > 0 || institutionalScore > 0 || partnerTriggers.length > 0) {
    const ev: FilterEvidence[] = []
    if (foreignScore > 0) ev.push({ label: '외국인 지분', value: '10%+ 확보', positive: true })
    if (institutionalScore > 0) ev.push({ label: '기관 지분', value: '30%+ 확보', positive: true })
    partnerTriggers.slice(0, 2).forEach(e =>
      ev.push({ label: e.event_type, value: e.summary.slice(0, 35) + (e.summary.length > 35 ? '…' : ''), positive: true })
    )
    const hasQuantScore = foreignScore > 0 || institutionalScore > 0

    candidates.push({
      cat: '빅테크_파트너',
      score: foreignScore * 3 + institutionalScore * 3 + partnerTriggers.length * 4,
      reason: {
        headline: '스마트머니 선행 진입 — 정보 비대칭 구간에서 대형 자금 축적 중',
        evidence: ev,
        why100x: '외국인/기관의 대규모 지분 축적은 미공개 대형 계약이나 구조 변화를 앞서 감지한 결과인 경우가 많습니다. 이들이 매집 완료 후 공시가 나오면 주가가 급격히 반응합니다.',
        confidence: hasQuantScore && partnerTriggers.length > 0 ? 'high' : 'medium',
      },
    })
  }

  // ── 5. 임상_파이프라인 ──────────────────────────────────────────────────────
  const clinicalTriggers = events.filter(e => e.rise_category === '임상_파이프라인')
  if (clinicalTriggers.length > 0) {
    candidates.push({
      cat: '임상_파이프라인',
      score: clinicalTriggers[0].confidence * 30,
      reason: {
        headline: 'FDA/식약처 임상 단계 진행 — 다음 단계 전환 시 밸류에이션 전면 재평가',
        evidence: clinicalTriggers.slice(0, 3).map(e => ({
          label: e.event_type,
          value: e.summary.slice(0, 40) + (e.summary.length > 40 ? '…' : ''),
          positive: true,
        })),
        why100x: '임상 단계별 성공 확률을 반영한 확률조정 NPV에서 다음 단계 진입 시 리스크 프리미엄이 급락하고 피크 매출 기준 밸류에이션으로 전환됩니다. 각 단계 전환이 독립적인 10배 모멘트입니다.',
        confidence: clinicalTriggers[0].confidence >= 0.6 ? 'high' : 'medium',
      },
    })
  }

  // ── 6. 정책_수혜 ────────────────────────────────────────────────────────────
  const policyTriggers = events.filter(e => ['규제_해소', '지정학_수혜'].includes(e.event_type))
  if (policyTriggers.length > 0) {
    candidates.push({
      cat: '정책_수혜',
      score: policyTriggers[0].confidence * 20,
      reason: {
        headline: '정책/지정학 tailwind — 정부 수요 또는 규제 해소로 수주 파이프라인 팽창',
        evidence: policyTriggers.slice(0, 2).map(e => ({
          label: e.event_type,
          value: e.summary.slice(0, 40) + (e.summary.length > 40 ? '…' : ''),
          positive: true,
        })),
        why100x: '정책 수혜 산업은 정부 예산이 앞세운 수요 폭발로 단기간에 기업 규모가 10배 이상 커지는 사례가 반복됩니다. 수주 잔고가 빠르게 쌓이는 구간이 최적 진입점입니다.',
        confidence: 'medium',
      },
    })
  }

  // ── 7. 공급_병목 ────────────────────────────────────────────────────────────
  const bottleneckTriggers = events.filter(e => ['공급_병목', '원자재_가격'].includes(e.event_type))
  if (bottleneckTriggers.length > 0) {
    candidates.push({
      cat: '공급_병목',
      score: bottleneckTriggers[0].confidence * 15,
      reason: {
        headline: '공급 제약 구간 수혜 — 수요 초과 상황에서 가격 결정력 확보',
        evidence: bottleneckTriggers.slice(0, 2).map(e => ({
          label: e.event_type,
          value: e.summary.slice(0, 40) + (e.summary.length > 40 ? '…' : ''),
          positive: true,
        })),
        why100x: '공급이 제한된 상황에서 수요가 급증하면 가격이 급등하고 마진이 폭발적으로 개선됩니다. 희소성이 지속되는 동안 기업은 시장을 독점하는 것과 유사한 이익 구조를 갖습니다.',
        confidence: 'medium',
      },
    })
  }

  if (candidates.length === 0) return null
  candidates.sort((a, b) => b.score - a.score)
  const top = candidates[0]
  const secondaryCategories = candidates
    .slice(1, 3)
    .filter(c => c.score >= top.score * 0.4)
    .map(c => c.cat)

  return {
    category: top.cat,
    ...top.reason,
    secondaryCategories,
  }
}

// ── Helpers ──────────────────────────────────────────────────────────────────

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

function buildCategorySummary(cat: string, scoresMap: Record<string, number> | null | undefined): string | null {
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

// ── RiseReasonPanel ───────────────────────────────────────────────────────────

function ConfidencePip({ level }: { level: 'high' | 'medium' | 'low' }) {
  const colors = { high: 'bg-[var(--color-success)]', medium: 'bg-[var(--color-gold)]', low: 'bg-[var(--color-text-2)]' }
  const labels = { high: '근거 강함', medium: '근거 보통', low: '근거 약함' }
  return (
    <span className="flex items-center gap-1 text-[10px] text-[var(--color-text-2)]">
      <span className={`inline-block w-2 h-2 rounded-full ${colors[level]}`} />
      {labels[level]}
    </span>
  )
}

function RiseReasonPanel({ reason }: { reason: RiseReason }) {
  const meta = RISE_CATEGORY_META[reason.category]
  return (
    <div className={`rounded-lg border border-current/20 p-4 space-y-3 ${meta.bg.replace('/15', '/8')}`}>
      <div className="flex items-start justify-between gap-3 flex-wrap">
        <div className="space-y-1">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-xs font-semibold text-[var(--color-text-2)]">100X 상승 판단 근거</span>
            <RiseCategoryBadge category={reason.category} />
            {reason.secondaryCategories.map(cat => (
              <RiseCategoryBadge key={cat} category={cat} />
            ))}
          </div>
          <p className={`text-sm font-medium ${meta.color}`}>{reason.headline}</p>
        </div>
        <ConfidencePip level={reason.confidence} />
      </div>

      {/* Evidence */}
      <div className="grid grid-cols-2 gap-x-4 gap-y-1 sm:grid-cols-3">
        {reason.evidence.map((ev, i) => (
          <div key={i} className="flex items-start gap-1.5">
            <span className={`shrink-0 text-xs mt-0.5 ${ev.positive ? 'text-[var(--color-success)]' : 'text-[var(--color-error)]'}`}>
              {ev.positive ? '✓' : '✗'}
            </span>
            <div>
              <p className="text-[10px] text-[var(--color-text-2)] leading-tight">{ev.label}</p>
              <p className={`text-xs font-medium leading-tight ${ev.positive ? 'text-[var(--color-text-1)]' : 'text-[var(--color-error)]'}`}>
                {ev.value}
              </p>
            </div>
          </div>
        ))}
      </div>

      {/* Why 100x */}
      <details className="group">
        <summary className="cursor-pointer text-xs text-[var(--color-text-2)] hover:text-[var(--color-text-1)] list-none flex items-center gap-1">
          <span className="group-open:hidden">▶</span>
          <span className="hidden group-open:inline">▼</span>
          왜 100배인가?
        </summary>
        <p className="mt-2 text-xs text-[var(--color-text-2)] leading-relaxed border-l-2 border-[var(--color-border)] pl-3">
          {reason.why100x}
        </p>
      </details>
    </div>
  )
}

// ── Main Page ─────────────────────────────────────────────────────────────────

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
  const riseReason = score?.passed
    ? deriveRiseReason(score.scores_by_filter, financials, priceContext, events)
    : null

  return (
    <div className="space-y-6">
      {/* Hero */}
      <div className="rounded-lg bg-[var(--color-surface)] border border-[var(--color-border)] p-6">
        <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3 sm:gap-4">
          <div className="min-w-0">
            <div className="flex items-center gap-2 sm:gap-3 flex-wrap">
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
              {riseReason && <RiseCategoryBadge category={riseReason.category} />}
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
            <div className="sm:text-right shrink-0">
              <div className="text-3xl font-bold text-[var(--color-text-1)]">{Math.round(score.score_10x ?? 0)}</div>
              <div className="text-xs text-[var(--color-text-2)]">10X Score</div>
              {score.percentile > 0 && (
                <div className="text-xs text-[var(--color-accent)] mt-0.5">상위 {(100 - score.percentile).toFixed(0)}%</div>
              )}
            </div>
          )}
        </div>
      </div>

      <div className="flex flex-col md:flex-row md:gap-6">
        {/* Main content */}
        <div className="flex-1 min-w-0 space-y-4 order-2 md:order-1">
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
              {/* 100X 판단 근거 패널 — 필터 통과 종목에만 표시 */}
              {riseReason && <RiseReasonPanel reason={riseReason} />}

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
                    {financials.order_backlog != null && (
                      <MetricRow
                        label="수주잔고"
                        value={fmtBillion(financials.order_backlog)}
                        ok={true}
                        sub={financials.revenue_ttm && financials.revenue_ttm > 0
                          ? `BCR ${(financials.order_backlog / financials.revenue_ttm).toFixed(1)}x`
                          : undefined}
                      />
                    )}
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
                    <table className="w-full text-xs min-w-[420px]">
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
                          {ev.rise_category && <RiseCategoryBadge category={ev.rise_category} />}
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
          <div className="w-full md:w-48 md:shrink-0 md:sticky md:top-20 md:self-start order-1 md:order-2 mb-4 md:mb-0">
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
