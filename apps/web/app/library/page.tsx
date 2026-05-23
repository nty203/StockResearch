'use client'
export const runtime = 'edge'

import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import type { RiseCategory } from '@stock/shared'
import { RiseCategoryBadge, RISE_CATEGORY_META } from '@/components/ui/rise-category-badge'

interface LibraryStockEntry {
  ticker: string
  name: string | null
  market: string | null
  peak_multiplier: number | null
  latest_multiplier: number | null
  earliest_signal_date: string | null
  rise_start_date: string | null
  price_at_rise_start: number | null
  latest_updated_at: string | null
  categories: Array<{
    category: string
    pre_rise_signals: Record<string, unknown> | null
    notes: string | null
    pptr_analysis: Record<string, unknown> | null
  }>
}

interface LibraryResponse {
  stocks: LibraryStockEntry[]
  count: number
}

const CATEGORY_GROUPS = Object.keys(RISE_CATEGORY_META) as RiseCategory[]

export default function LibraryPage() {
  const [catFilter, setCatFilter] = useState<RiseCategory | 'ALL'>('ALL')

  const { data, isLoading, error } = useQuery<LibraryResponse>({
    queryKey: ['hundredxLibrary'],
    queryFn: async () => {
      const res = await fetch('/api/hundredx/library')
      if (!res.ok) return { stocks: [], count: 0 }
      return res.json()
    },
    staleTime: 5 * 60_000,
  })

  const libStocks = data?.stocks ?? []
  const filtered =
    catFilter === 'ALL'
      ? libStocks
      : libStocks.filter(s => s.categories.some(c => c.category === catFilter))

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-xl font-semibold text-[var(--color-text-1)]">
          100배 라이브러리
        </h1>
        <p className="text-sm text-[var(--color-text-2)] mt-1">
          과거 5~107배 종목 — peak는 historical 최고치, latest는 매주 현재가 기준 갱신 (100배 점진 추종)
        </p>
      </div>

      {/* 카테고리 필터 */}
      <div className="flex flex-wrap gap-1.5">
        <button
          onClick={() => setCatFilter('ALL')}
          className={`text-xs px-2.5 py-1 rounded border transition-colors ${
            catFilter === 'ALL'
              ? 'bg-[var(--color-accent)]/20 border-[var(--color-accent)] text-[var(--color-accent)]'
              : 'border-[var(--color-border)] text-[var(--color-text-2)]'
          }`}
        >
          전체 ({libStocks.length})
        </button>
        {CATEGORY_GROUPS.map(cat => {
          const meta = RISE_CATEGORY_META[cat]
          const active = catFilter === cat
          const count = libStocks.filter(s =>
            s.categories.some(c => c.category === cat)
          ).length
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
              {meta.label} ({count})
            </button>
          )
        })}
      </div>

      {isLoading && (
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="h-32 rounded-lg bg-[var(--color-surface)] animate-pulse" />
          ))}
        </div>
      )}

      {error && (
        <div className="rounded-lg bg-[var(--color-surface)] border border-[var(--color-error)] p-4 text-sm text-[var(--color-error)]">
          라이브러리 데이터를 불러오지 못했습니다.
        </div>
      )}

      {!isLoading && !error && filtered.length === 0 && (
        <div className="rounded-lg bg-[var(--color-surface)] border border-[var(--color-border)] p-8 text-center">
          <p className="text-sm text-[var(--color-text-2)]">
            {catFilter === 'ALL' ? '라이브러리가 비어있습니다.' : `${RISE_CATEGORY_META[catFilter as RiseCategory]?.label} 카테고리 종목 없음`}
          </p>
          <p className="text-xs text-[var(--color-text-2)] mt-1">
            매월 1일 03시 KST에 자동 발견 워크플로우가 실행되어 라이브러리가 갱신됩니다.
          </p>
        </div>
      )}

      {filtered.length > 0 && (
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
          {filtered.map(stock => (
            <ReferenceCard key={`${stock.ticker}-${stock.rise_start_date}`} stock={stock} />
          ))}
        </div>
      )}

      {/* 카테고리 가이드 */}
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
  )
}

function ReferenceCard({ stock }: { stock: LibraryStockEntry }) {
  const [expanded, setExpanded] = useState(false)
  const peak = stock.peak_multiplier ?? 0
  const latest = stock.latest_multiplier ?? 0
  const isLive = latest >= 1 && stock.latest_updated_at != null
  const towardHundred = latest >= 50
  const isAutoDiscovered = stock.categories.every(c => (c.category as string) === '미분류')

  return (
    <div
      className="rounded-lg bg-[var(--color-surface)] border border-[var(--color-border)] p-3 cursor-pointer hover:border-[var(--color-accent)]/50 transition-colors"
      onClick={() => setExpanded(v => !v)}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="space-y-1 min-w-0">
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="text-sm font-semibold text-[var(--color-text-1)]">
              {stock.name ?? stock.ticker}
            </span>
            <span className="text-xs text-[var(--color-text-2)]">{stock.ticker}</span>
            {stock.market && (
              <span className="text-xs px-1.5 py-0.5 rounded bg-[var(--color-card)] text-[var(--color-text-2)]">
                {stock.market}
              </span>
            )}
            {isAutoDiscovered && (
              <span
                className="text-[10px] px-1.5 py-0.5 rounded bg-[var(--color-accent)]/15 text-[var(--color-accent)]"
                title="5년 가격 데이터에서 자동 발견 — 시그널 추출 대기"
              >
                자동 발견
              </span>
            )}
          </div>
          <div className="flex flex-wrap gap-1">
            {stock.categories.map(c => (
              <RiseCategoryBadge key={c.category} category={c.category} />
            ))}
          </div>
        </div>
        <div className="text-right shrink-0">
          <div className={`text-lg font-bold ${towardHundred ? 'text-[var(--color-gold)]' : 'text-[var(--color-text-1)]'}`}>
            {peak.toFixed(0)}x
          </div>
          {isLive && (
            <div className="text-[10px] text-[var(--color-text-2)]">
              현재 <span className={latest >= peak ? 'text-[var(--color-success)]' : 'text-[var(--color-text-1)]'}>{latest.toFixed(1)}x</span>
            </div>
          )}
          {stock.rise_start_date && (
            <div className="text-[10px] text-[var(--color-text-2)]">{stock.rise_start_date.slice(0, 7)}</div>
          )}
        </div>
      </div>

      {expanded && (
        <div className="mt-3 pt-3 border-t border-[var(--color-border)] space-y-2">
          {stock.earliest_signal_date && stock.rise_start_date && (
            <div className="text-xs text-[var(--color-text-2)]">
              <span>선행 기간: </span>
              <span className="text-[var(--color-accent)]">
                {stock.earliest_signal_date.slice(0, 7)} → {stock.rise_start_date.slice(0, 7)} 상승 시작
              </span>
            </div>
          )}
          {stock.latest_updated_at && (
            <div className="text-xs text-[var(--color-text-2)]">
              <span>최근 갱신: </span>
              <span>{new Date(stock.latest_updated_at).toLocaleDateString('ko-KR')}</span>
              <span className="ml-2">peak <span className="text-[var(--color-gold)]">{peak.toFixed(1)}x</span></span>
              <span className="ml-2">latest <span className="text-[var(--color-text-1)]">{latest.toFixed(2)}x</span></span>
            </div>
          )}
          <div>
            <p className="text-xs font-medium text-[var(--color-text-2)] mb-1">카테고리별 선행 신호</p>
            <ul className="space-y-1">
              {stock.categories.map((c, i) => {
                const pptr = c.pptr_analysis as any
                return (
                  <li key={i} className="text-xs text-[var(--color-text-2)] flex flex-col gap-1.5">
                    <div className="flex gap-1.5">
                      <span className="text-[var(--color-accent)] shrink-0 mt-0.5">•</span>
                      <span>
                        <RiseCategoryBadge category={c.category} />{' '}
                        {c.notes ?? '(설명 없음)'}
                      </span>
                    </div>
                    {pptr && pptr.conclusion && (
                      <div className="ml-3 mt-1 p-2 rounded bg-[var(--color-background)] border border-[var(--color-border)]">
                        <p className="font-semibold text-[var(--color-text-1)] mb-1">왜 올랐는가? (PPTR)</p>
                        <p className="text-[var(--color-accent)] mb-1">{pptr.conclusion.most_likely_cause}</p>
                        <ul className="list-disc list-inside space-y-0.5 opacity-80 pl-1">
                          {pptr.conclusion.top3_traces?.map((t: string, ti: number) => (
                            <li key={ti}>{t}</li>
                          ))}
                        </ul>
                        {pptr.resolutions?.[0]?.detector_rule && (
                          <div className="mt-2 text-[10px] text-[var(--color-text-2)] border-t border-[var(--color-border)] pt-1">
                            <span className="font-medium">탐지 규칙:</span> {JSON.stringify(pptr.resolutions[0].detector_rule.conditions)}
                          </div>
                        )}
                      </div>
                    )}
                  </li>
                )
              })}
            </ul>
          </div>
        </div>
      )}
    </div>
  )
}
