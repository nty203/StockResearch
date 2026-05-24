'use client'
export const runtime = 'edge'

import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import type { RiseCategory } from '@stock/shared'
import { RiseCategoryBadge, RISE_CATEGORY_META } from '@/components/ui/rise-category-badge'

interface Evidence {
  source_type: string
  source_id: string
  text_excerpt: string
  date: string | null
  amount: number | null
}

interface AnalogRef {
  ticker: string
  name: string
  date: string | null
  multiplier: number | null
}

interface FingerprintInfo {
  score: number
  matched: string[]
  missing: string[]
  details: Record<string, unknown>
}

interface FiredTrigger {
  seq: number
  name: string
  months_from_rise: number
  fired_at_date: string | null
  fired_at_months_ago: number | null
  weight: number
  matched_signals: string[]
}

interface TimelineProgress {
  library_ticker: string
  library_name: string
  library_category: string
  library_peak_multiplier: number | null
  fired_triggers: FiredTrigger[]
  total_triggers: number
  trajectory_score: number
  current_position_months: number
  next_expected: { seq: number; name: string; months_from_rise: number; expected_in_months: number } | null
}

interface PptrMatch {
  library_ticker: string
  library_name: string
  producer_id: string
  matched_conditions: string[]
}

interface CategoryEntry {
  category: RiseCategory
  confidence: number
  evidence: Evidence[]
  first_detected_at: string | null
  detected_at: string
  analog: AnalogRef | null
  fingerprint: FingerprintInfo | null
  timeline: TimelineProgress | null
  pptr: PptrMatch | null
}

interface StockResult {
  ticker: string
  stock: {
    ticker: string
    name_kr: string | null
    name_en: string | null
    market: string | null
    sector_tag: string | null
  } | null
  conviction: number
  grade: 'S' | 'A' | 'B' | 'C'
  best_fingerprint_score: number | null
  first_signal_at: string | null
  price_performance: {
    baseline_date: string | null
    baseline_close: number | null
    latest_date: string | null
    latest_close: number | null
    peak_date: string | null
    peak_close: number | null
    current_multiplier: number | null
    change_pct: number | null
    peak_multiplier: number | null
    peak_change_pct: number | null
    updated_at: string | null
  } | null
  categories: CategoryEntry[]
}

interface ApiResponse {
  results: StockResult[]
  count: number
  grade_counts?: { S: number; A: number; B: number; C: number }
}

const CONFIDENCE_PRESETS = [0.5, 0.7, 0.9] as const
const GRADE_META = {
  S: { label: 'S', desc: '라이브러리 패턴 고일치 + 높은 Conviction', bg: 'bg-[var(--color-gold)]/20', color: 'text-[var(--color-gold)]', border: 'border-[var(--color-gold)]/50' },
  A: { label: 'A', desc: '라이브러리 패턴 일치 또는 높은 Conviction', bg: 'bg-[var(--color-success)]/15', color: 'text-[var(--color-success)]', border: 'border-[var(--color-success)]/40' },
  B: { label: 'B', desc: '부분 패턴 일치 또는 중간 Conviction', bg: 'bg-[var(--color-accent)]/10', color: 'text-[var(--color-accent)]', border: 'border-[var(--color-accent)]/30' },
  C: { label: 'C', desc: '신뢰도 기준 통과 (패턴 미확인)', bg: 'bg-[var(--color-card)]', color: 'text-[var(--color-text-2)]', border: 'border-[var(--color-border)]' },
} as const

export default function HundredxPage() {
  const [minConfidence, setMinConfidence] = useState<number>(0.5)
  const [gradeFilter, setGradeFilter] = useState<'ALL' | 'S' | 'A' | 'B' | 'C'>('ALL')
  const [expanded, setExpanded] = useState<Set<string>>(new Set())

  const { data, isLoading, error } = useQuery<ApiResponse>({
    queryKey: ['hundredx', minConfidence],
    queryFn: async () => {
      const res = await fetch(`/api/hundredx?min_confidence=${minConfidence}`)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      return res.json()
    },
    staleTime: 60_000,
    refetchInterval: 60_000,
    retry: false,
  })

  const toggle = (ticker: string) => {
    setExpanded(prev => {
      const next = new Set(prev)
      if (next.has(ticker)) next.delete(ticker)
      else next.add(ticker)
      return next
    })
  }

  return (
    <div className="space-y-5">
      <div className="flex items-start justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-xl font-semibold text-[var(--color-text-1)]">100배 시그널</h1>
          <p className="text-sm text-[var(--color-text-2)] mt-1">
            7개 카테고리 동시 탐지 — 과거 100배 종목 패턴과 정량 비교
          </p>
        </div>

        {/* Confidence threshold toggle */}
        <div className="flex items-center gap-2">
          <span className="text-xs text-[var(--color-text-2)]">최소 신뢰도</span>
          <div className="inline-flex rounded border border-[var(--color-border)] overflow-hidden">
            {CONFIDENCE_PRESETS.map(c => (
              <button
                key={c}
                onClick={() => setMinConfidence(c)}
                className={`text-xs px-3 py-1.5 transition-colors ${
                  minConfidence === c
                    ? 'bg-[var(--color-accent)]/20 text-[var(--color-accent)]'
                    : 'text-[var(--color-text-2)] hover:text-[var(--color-text-1)]'
                }`}
              >
                {Math.round(c * 100)}%
              </button>
            ))}
          </div>
        </div>
      </div>

      {isLoading && (
        <div className="space-y-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="h-32 rounded-lg bg-[var(--color-surface)] animate-pulse" />
          ))}
        </div>
      )}

      {error && (
        <div className="rounded-lg bg-[var(--color-surface)] border border-[var(--color-error)] p-4 text-sm text-[var(--color-error)]">
          데이터를 불러오지 못했습니다.
        </div>
      )}

      {/* Grade filter bar */}
      {(data?.results?.length ?? 0) > 0 && (
        <div className="flex flex-wrap gap-1.5">
          <button
            onClick={() => setGradeFilter('ALL')}
            className={`text-xs px-2.5 py-1 rounded border transition-colors ${
              gradeFilter === 'ALL'
                ? 'bg-[var(--color-accent)]/20 border-[var(--color-accent)] text-[var(--color-accent)]'
                : 'border-[var(--color-border)] text-[var(--color-text-2)]'
            }`}
          >
            전체 ({data?.results?.length ?? 0})
          </button>
          {(['S', 'A', 'B', 'C'] as const).map(g => {
            const meta = GRADE_META[g]
            const cnt = data?.grade_counts?.[g] ?? data?.results?.filter(r => r.grade === g).length ?? 0
            return (
              <button
                key={g}
                onClick={() => setGradeFilter(g)}
                className={`text-xs px-2.5 py-1 rounded border transition-colors font-medium ${
                  gradeFilter === g
                    ? `${meta.bg} ${meta.color} ${meta.border}`
                    : 'border-[var(--color-border)] text-[var(--color-text-2)]'
                }`}
              >
                {g} ({cnt})
              </button>
            )
          })}
        </div>
      )}

      {!isLoading && !error && (data?.results?.length ?? 0) === 0 && (
        <div className="rounded-lg bg-[var(--color-surface)] border border-[var(--color-border)] p-8 text-center">
          <p className="text-sm text-[var(--color-text-2)]">
            현재 임계값({Math.round(minConfidence * 100)}%) 이상의 카테고리 탐지 종목이 없습니다.
          </p>
          <p className="text-xs text-[var(--color-text-2)] mt-1">
            매일 06:00 KST에 100배 시그널 스캐너가 실행됩니다.
          </p>
        </div>
      )}

      {(data?.results?.length ?? 0) > 0 && (
        <div className="space-y-3">
          {(() => {
            const filtered = gradeFilter === 'ALL'
              ? data!.results
              : data!.results.filter(r => r.grade === gradeFilter)
            return (
              <>
                <div className="text-xs text-[var(--color-text-2)]">
                  {filtered.length}개 종목 {gradeFilter !== 'ALL' && `(등급 ${gradeFilter})`} — Conviction + 등급 순
                </div>
                {filtered.map(result => (
                  <StockCard
                    key={result.ticker}
                    result={result}
                    expanded={expanded.has(result.ticker)}
                    onToggle={() => toggle(result.ticker)}
                  />
                ))}
              </>
            )
          })()}
        </div>
      )}
    </div>
  )
}

function StockCard({
  result,
  expanded,
  onToggle,
}: {
  result: StockResult
  expanded: boolean
  onToggle: () => void
}) {
  const name = result.stock?.name_kr || result.stock?.name_en || result.ticker
  const market = result.stock?.market
  const sector = result.stock?.sector_tag
  const grade = result.grade ?? 'C'
  const gradeMeta = GRADE_META[grade]

  const firstSignalText = result.first_signal_at
    ? formatRelativeDays(result.first_signal_at)
    : null

  // Conviction color: green ≥70, yellow ≥45, gray <45
  const convictionColor =
    result.conviction >= 70 ? 'text-[var(--color-success)]' :
    result.conviction >= 45 ? 'text-[var(--color-warning)]' :
    'text-[var(--color-text-1)]'

  return (
    <div className={`rounded-lg bg-[var(--color-surface)] border overflow-hidden ${
      grade === 'S' ? 'border-[var(--color-gold)]/40' :
      grade === 'A' ? 'border-[var(--color-success)]/30' :
      'border-[var(--color-border)]'
    }`}>
      {/* Header */}
      <button
        onClick={onToggle}
        className="w-full p-4 flex items-start justify-between gap-4 hover:bg-[var(--color-card)]/30 transition-colors text-left"
      >
        <div className="space-y-1.5 min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            {/* Grade badge */}
            <span className={`text-[11px] font-bold px-1.5 py-0.5 rounded border ${gradeMeta.bg} ${gradeMeta.color} ${gradeMeta.border}`}
              title={gradeMeta.desc}>
              {grade}
            </span>
            <span className="text-base font-semibold text-[var(--color-text-1)]">
              {name}
            </span>
            <span className="text-xs text-[var(--color-text-2)]">
              {result.ticker}
            </span>
            {market && (
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-[var(--color-card)] text-[var(--color-text-2)]">
                {market}
              </span>
            )}
            {sector && (
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-[var(--color-card)]/60 text-[var(--color-text-2)]">
                {sector}
              </span>
            )}
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {result.categories.map(c => (
              <RiseCategoryBadge key={c.category} category={c.category} />
            ))}
          </div>
        </div>

        <div className="text-right shrink-0">
          <div className={`text-xl font-bold ${convictionColor}`}>
            {result.conviction.toFixed(1)}
          </div>
          <div className="text-[10px] text-[var(--color-text-2)]">Conviction</div>
          {result.best_fingerprint_score != null && result.best_fingerprint_score > 0 && (
            <div className="text-[10px] text-[var(--color-text-2)] mt-0.5">
              패턴 <span className={result.best_fingerprint_score >= 0.5 ? 'text-[var(--color-success)]' : 'text-[var(--color-text-1)]'}>
                {Math.round(result.best_fingerprint_score * 100)}%
              </span>
            </div>
          )}
          <div className="text-xs text-[var(--color-text-2)] mt-1">
            {result.categories.length}/7 카테고리
          </div>
          {firstSignalText && (
            <div className="text-[10px] text-[var(--color-text-2)] mt-1">
              첫 신호 {firstSignalText}
            </div>
          )}
          {result.price_performance?.change_pct != null && (
            <div className="text-[10px] text-[var(--color-text-2)] mt-1 leading-tight">
              <span>상승 </span>
              <span className={result.price_performance.change_pct >= 0 ? 'text-[var(--color-success)]' : 'text-[var(--color-error)]'}>
                {formatReturnPct(result.price_performance.change_pct)}
              </span>
              {result.price_performance.current_multiplier != null && (
                <span className="ml-1">
                  ({result.price_performance.current_multiplier.toFixed(1)}x)
                </span>
              )}
              {result.price_performance.baseline_date && (
                <div>{result.price_performance.baseline_date.slice(0, 7)} 저점</div>
              )}
            </div>
          )}
        </div>
      </button>

      {/* Expanded category details */}
      {expanded && (
        <div className="border-t border-[var(--color-border)] p-4 space-y-3">
          {result.categories.map(cat => (
            <CategoryDetail key={cat.category} cat={cat} ticker={result.ticker} />
          ))}
        </div>
      )}
    </div>
  )
}

function CategoryDetail({ cat, ticker }: { cat: CategoryEntry; ticker: string }) {
  const meta = RISE_CATEGORY_META[cat.category]
  const isNew = cat.first_detected_at &&
    Date.now() - new Date(cat.first_detected_at).getTime() < 7 * 86400_000

  return (
    <div className="rounded border border-[var(--color-border)] p-3 bg-[var(--color-card)]/30">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <RiseCategoryBadge category={cat.category} />
          {isNew && (
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-[var(--color-accent)]/20 text-[var(--color-accent)] font-medium">
              NEW
            </span>
          )}
        </div>
        <div className="text-xs text-[var(--color-text-2)]">
          신뢰도 {Math.round(cat.confidence * 100)}%
        </div>
      </div>

      <p className="text-[11px] text-[var(--color-text-2)] mb-2">{meta.desc}</p>

      {/* Evidence list */}
      <div className="space-y-1.5">
        {cat.evidence
          .filter(e => e.source_type !== 'bcr' && e.source_type !== 'opm_delta') // hide internal markers
          .map((ev, i) => (
            <EvidenceRow key={i} evidence={ev} />
          ))}
      </div>

      {/* Timeline progress — 100배 종목의 trigger sequence 진행도 */}
      {cat.timeline && cat.timeline.fired_triggers.length > 0 && (
        <TimelineCard timeline={cat.timeline} />
      )}

      {/* PPTR Match — 라이브러리 PPTR 원인 패턴 일치 */}
      {cat.pptr && (
        <div className="mt-2 pt-2 border-t border-[var(--color-border)] space-y-1.5 bg-[var(--color-accent)]/5 rounded p-2 border-l-2 border-l-[var(--color-accent)]">
          <p className="text-xs font-semibold text-[var(--color-accent)]">PPTR 원인 패턴 매칭</p>
          <p className="text-[11px] text-[var(--color-text-2)] leading-relaxed">
            이 종목은 라이브러리 <span className="text-[var(--color-text-1)] font-medium">{cat.pptr.library_name ?? cat.pptr.library_ticker}</span>의 핵심 원인 패턴(<span className="text-[var(--color-text-1)]">{cat.pptr.producer_id}</span>)과 일치합니다.
          </p>
          <div className="flex flex-wrap gap-1 mt-1">
            {cat.pptr.matched_conditions.map((cond, idx) => (
              <span key={idx} className="text-[10px] px-1.5 py-0.5 rounded bg-[var(--color-surface)] border border-[var(--color-border)] text-[var(--color-text-2)]">
                ✓ {cond}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Fingerprint match — 100배 종목 패턴과의 유사도 */}
      {cat.fingerprint && cat.analog && (
        <FingerprintCard fingerprint={cat.fingerprint} analog={cat.analog} />
      )}

      {/* Analog reference (fingerprint 없을 때만 단독 표시) */}
      {!cat.fingerprint && cat.analog && (
        <div className="mt-2 pt-2 border-t border-[var(--color-border)] text-xs text-[var(--color-text-2)]">
          <span>유사 종목: </span>
          <span className="text-[var(--color-text-1)]">{cat.analog.name ?? cat.analog.ticker}</span>
          {cat.analog.date && (
            <span className="ml-1">({cat.analog.date.slice(0, 7)})</span>
          )}
          {cat.analog.multiplier && (
            <span className="ml-1 text-[var(--color-accent)]">
              → {cat.analog.multiplier}배
            </span>
          )}
        </div>
      )}
    </div>
  )
}

function FingerprintCard({ fingerprint, analog }: { fingerprint: FingerprintInfo; analog: AnalogRef }) {
  const score = Math.round(fingerprint.score * 100)
  const scoreColor =
    score >= 70 ? 'text-[var(--color-success)]' :
    score >= 40 ? 'text-[var(--color-warning)]' :
    'text-[var(--color-text-2)]'

  return (
    <div className="mt-2 pt-2 border-t border-[var(--color-border)] space-y-1.5">
      <div className="flex items-center justify-between gap-2">
        <div className="text-xs">
          <span className="text-[var(--color-text-2)]">패턴 유사도: </span>
          <span className={`font-bold ${scoreColor}`}>{score}%</span>
          <span className="text-[var(--color-text-2)] ml-2">vs </span>
          <span className="text-[var(--color-text-1)]">{analog.name ?? analog.ticker}</span>
          {analog.date && (
            <span className="text-[var(--color-text-2)] ml-1">({analog.date.slice(0, 7)})</span>
          )}
          {analog.multiplier && (
            <span className="text-[var(--color-gold)] ml-1">→ {analog.multiplier}배</span>
          )}
        </div>
      </div>

      {/* Matched/missing dimensions */}
      <div className="flex flex-wrap gap-1">
        {fingerprint.matched.map((dim, i) => (
          <span
            key={`m-${i}`}
            className="text-[10px] px-1.5 py-0.5 rounded bg-[var(--color-success)]/15 text-[var(--color-success)]"
            title="매칭된 차원"
          >
            ✓ {prettyDim(dim)}
          </span>
        ))}
        {fingerprint.missing.map((dim, i) => (
          <span
            key={`x-${i}`}
            className="text-[10px] px-1.5 py-0.5 rounded bg-[var(--color-error)]/10 text-[var(--color-text-2)]"
            title="누락된 차원"
          >
            ✗ {prettyDim(dim)}
          </span>
        ))}
      </div>
    </div>
  )
}

function TimelineCard({ timeline }: { timeline: TimelineProgress }) {
  const score = Math.round(timeline.trajectory_score * 100)
  const scoreColor =
    score >= 70 ? 'text-[var(--color-success)]' :
    score >= 40 ? 'text-[var(--color-warning)]' :
    'text-[var(--color-text-2)]'

  // Build full timeline (fired + remaining) sorted by seq
  const firedSeqs = new Set(timeline.fired_triggers.map(t => t.seq))
  const allTriggers = [
    ...timeline.fired_triggers.map(t => ({ ...t, fired: true })),
  ]
  // Add the next_expected as a "future" entry
  if (timeline.next_expected) {
    allTriggers.push({
      seq: timeline.next_expected.seq,
      name: timeline.next_expected.name,
      months_from_rise: timeline.next_expected.months_from_rise,
      fired_at_date: null,
      fired_at_months_ago: null,
      weight: 0,
      matched_signals: [],
      fired: false,
    } as FiredTrigger & { fired: boolean })
  }
  allTriggers.sort((a, b) => a.seq - b.seq)

  const peak = timeline.library_peak_multiplier
  const positionLabel = timeline.current_position_months >= 0
    ? `T+${timeline.current_position_months}개월`
    : `T${timeline.current_position_months}개월`

  return (
    <div className="mt-2 pt-2 border-t border-[var(--color-border)] space-y-2">
      <div className="flex items-baseline justify-between gap-2">
        <div className="text-xs text-[var(--color-text-2)]">
          <span className="font-medium text-[var(--color-text-1)]">Timeline 진행도: </span>
          <span className={`font-bold ${scoreColor}`}>{score}%</span>
          <span className="ml-2">
            {timeline.fired_triggers.length}/{timeline.total_triggers} 트리거 발화
          </span>
        </div>
        <div className="text-[10px] text-[var(--color-text-2)]">
          vs <span className="text-[var(--color-text-1)]">{timeline.library_name ?? timeline.library_ticker}</span>
          {peak && <span className="text-[var(--color-gold)] ml-1">→ {peak}배</span>}
          <span className="ml-1">현재 {positionLabel}</span>
        </div>
      </div>

      {/* Trigger steps */}
      <div className="space-y-1">
        {allTriggers.map((t, i) => (
          <TriggerStep key={`${t.seq}-${i}`} trigger={t} fired={(t as { fired: boolean }).fired} />
        ))}
      </div>

      {timeline.next_expected && (
        <div className="text-[10px] text-[var(--color-text-2)] italic pt-1">
          → 다음 예상: <span className="text-[var(--color-accent)]">{timeline.next_expected.name}</span>
          <span className="ml-1">
            ({timeline.next_expected.expected_in_months > 0 ? `${timeline.next_expected.expected_in_months}개월 후` : '예상 시점 도달'})
          </span>
        </div>
      )}
    </div>
  )
}

function TriggerStep({
  trigger, fired,
}: { trigger: FiredTrigger; fired: boolean }) {
  const monthLabel = trigger.months_from_rise >= 0
    ? `T+${trigger.months_from_rise}`
    : `T${trigger.months_from_rise}`
  const agoText = trigger.fired_at_months_ago != null
    ? `${trigger.fired_at_months_ago}개월 전 발화`
    : ''

  return (
    <div className={`flex items-center gap-2 text-xs ${fired ? '' : 'opacity-50'}`}>
      <span className={`shrink-0 w-4 h-4 rounded-full flex items-center justify-center text-[9px] font-bold ${
        fired
          ? 'bg-[var(--color-success)]/30 text-[var(--color-success)]'
          : 'bg-[var(--color-card)] text-[var(--color-text-2)] border border-dashed border-[var(--color-border)]'
      }`}>
        {fired ? '✓' : '?'}
      </span>
      <span className="shrink-0 text-[10px] text-[var(--color-text-2)] font-mono w-10">{monthLabel}</span>
      <span className="flex-1 text-[var(--color-text-1)]">{trigger.name}</span>
      {fired && agoText && (
        <span className="text-[10px] text-[var(--color-text-2)] shrink-0">{agoText}</span>
      )}
    </div>
  )
}

function prettyDim(raw: string): string {
  // quant.bcr_at_signal → BCR
  // quant.opm_at_signal → OPM 현재
  // quant.opm_prev → OPM 이전
  // quant.opm_delta_at_signal → OPM Δ
  // quant.backlog_yoy_pct → 수주잔고 YoY
  // quant.revenue_growth_yoy → 매출 YoY
  // sector=방산 → 섹터 방산
  // amount>=9000억 → 금액≥9000억
  // keywords(5/8) → 키워드 5/8
  if (raw.startsWith('quant.bcr')) return 'BCR'
  if (raw === 'quant.opm_at_signal') return 'OPM 현재'
  if (raw === 'quant.opm_prev') return 'OPM 이전'
  if (raw.startsWith('quant.opm_delta')) return 'OPM Δ'
  if (raw === 'quant.backlog_yoy_pct') return '수주잔고 YoY'
  if (raw === 'quant.revenue_growth_yoy') return '매출 YoY'
  if (raw.startsWith('sector=')) return '섹터'
  if (raw.startsWith('sector(')) return '섹터 불일치'
  if (raw.startsWith('amount>=')) return raw.replace('amount>=', '금액≥')
  if (raw.startsWith('amount<')) return '금액 미달'
  if (raw.startsWith('keywords(')) {
    const m = raw.match(/keywords\((\d+)\/(\d+)/)
    return m ? `키워드 ${m[1]}/${m[2]}` : '키워드'
  }
  return raw
}

function EvidenceRow({ evidence }: { evidence: Evidence }) {
  const sourceLabel = SOURCE_LABELS[evidence.source_type] || evidence.source_type
  return (
    <div className="text-xs text-[var(--color-text-2)] flex gap-2">
      <span className="shrink-0 text-[10px] px-1 py-0.5 rounded bg-[var(--color-surface)] text-[var(--color-text-1)] font-medium">
        {sourceLabel}
      </span>
      <span className="flex-1 line-clamp-2">
        {evidence.date && (
          <span className="text-[var(--color-text-2)]/70 mr-1">
            {evidence.date.slice(0, 10)}
          </span>
        )}
        {evidence.text_excerpt}
        {evidence.amount && evidence.source_type === 'filing' && (
          <span className="ml-1 text-[var(--color-text-1)]">({evidence.amount}억)</span>
        )}
      </span>
    </div>
  )
}

const SOURCE_LABELS: Record<string, string> = {
  filing: '공시',
  financials: '재무',
  keywords: '키워드',
  news: '뉴스',
  report: '리포트',
  llm_verdict: 'LLM검증',
}

function formatRelativeDays(iso: string): string {
  const days = Math.floor((Date.now() - new Date(iso).getTime()) / 86400_000)
  if (days === 0) return '오늘'
  if (days === 1) return '어제'
  if (days < 7) return `${days}일 전`
  if (days < 30) return `${Math.floor(days / 7)}주 전`
  if (days < 365) return `${Math.floor(days / 30)}개월 전`
  return `${Math.floor(days / 365)}년 전`
}

function formatReturnPct(value: number): string {
  const rounded = Math.round(value)
  const sign = rounded > 0 ? '+' : ''
  return `${sign}${rounded.toLocaleString('ko-KR')}%`
}
