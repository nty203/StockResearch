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
  date: string | null
  multiplier: number | null
}

interface CategoryEntry {
  category: RiseCategory
  confidence: number
  evidence: Evidence[]
  first_detected_at: string | null
  detected_at: string
  analog: AnalogRef | null
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
  first_signal_at: string | null
  golden_active: boolean
  categories: CategoryEntry[]
}

interface ApiResponse {
  results: StockResult[]
  count: number
}

const CONFIDENCE_PRESETS = [0.5, 0.7, 0.9] as const

export default function HundredxPage() {
  const [minConfidence, setMinConfidence] = useState<number>(0.5)
  const [expanded, setExpanded] = useState<Set<string>>(new Set())

  const { data, isLoading, error } = useQuery<ApiResponse>({
    queryKey: ['hundredx', minConfidence],
    queryFn: () =>
      fetch(`/api/hundredx?min_confidence=${minConfidence}`).then(r => r.json()),
    staleTime: 60_000,
    refetchInterval: 60_000,
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

      {!isLoading && !error && (data?.results.length ?? 0) === 0 && (
        <div className="rounded-lg bg-[var(--color-surface)] border border-[var(--color-border)] p-8 text-center">
          <p className="text-sm text-[var(--color-text-2)]">
            현재 임계값({Math.round(minConfidence * 100)}%) 이상의 카테고리 탐지 종목이 없습니다.
          </p>
          <p className="text-xs text-[var(--color-text-2)] mt-1">
            매일 06:00 KST에 100배 시그널 스캐너가 실행됩니다.
          </p>
        </div>
      )}

      {(data?.results.length ?? 0) > 0 && (
        <div className="space-y-3">
          <div className="text-xs text-[var(--color-text-2)]">
            {data?.count}개 종목 (Conviction 순)
          </div>
          {data?.results.map(result => (
            <StockCard
              key={result.ticker}
              result={result}
              expanded={expanded.has(result.ticker)}
              onToggle={() => toggle(result.ticker)}
            />
          ))}
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

  const firstSignalText = result.first_signal_at
    ? formatRelativeDays(result.first_signal_at)
    : null

  return (
    <div className="rounded-lg bg-[var(--color-surface)] border border-[var(--color-border)] overflow-hidden">
      {/* Header */}
      <button
        onClick={onToggle}
        className="w-full p-4 flex items-start justify-between gap-4 hover:bg-[var(--color-card)]/30 transition-colors text-left"
      >
        <div className="space-y-1.5 min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
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
            {result.golden_active && (
              <a
                href={`/signals?ticker=${result.ticker}`}
                onClick={e => e.stopPropagation()}
                className="text-[10px] px-1.5 py-0.5 rounded bg-[var(--color-gold)]/20 text-[var(--color-gold)] hover:underline"
              >
                /signals 골든
              </a>
            )}
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {result.categories.map(c => (
              <RiseCategoryBadge key={c.category} category={c.category} />
            ))}
          </div>
        </div>

        <div className="text-right shrink-0">
          <div className="text-xl font-bold text-[var(--color-accent)]">
            {result.conviction.toFixed(1)}
          </div>
          <div className="text-[10px] text-[var(--color-text-2)]">Conviction</div>
          <div className="text-xs text-[var(--color-text-2)] mt-1">
            {result.categories.length}/7 카테고리
          </div>
          {firstSignalText && (
            <div className="text-[10px] text-[var(--color-text-2)] mt-1">
              첫 신호 {firstSignalText}
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
          <a
            href={`/stocks/${result.ticker}`}
            className="block text-center text-xs text-[var(--color-accent)] hover:underline pt-2"
          >
            종목 상세 페이지 →
          </a>
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

      {/* Analog reference */}
      {cat.analog && (
        <div className="mt-2 pt-2 border-t border-[var(--color-border)] text-xs text-[var(--color-text-2)]">
          <span>유사 종목: </span>
          <span className="text-[var(--color-text-1)]">{cat.analog.ticker}</span>
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
