'use client'
export const runtime = 'edge'

import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import type { TriggerEvent, RiseCategory } from '@stock/shared'
import { RiseCategoryBadge, RISE_CATEGORY_META } from '@/components/ui/rise-category-badge'

interface SignalRow extends TriggerEvent {
  stocks?: { name_kr: string | null; name_en: string | null; market: string }
}

const ALL_CATEGORIES = Object.keys(RISE_CATEGORY_META) as RiseCategory[]

export default function SignalsPage() {
  const [filter, setFilter] = useState<RiseCategory | 'ALL'>('ALL')
  const [goldenOnly, setGoldenOnly] = useState(false)
  const [days, setDays] = useState(30)

  const { data, isLoading, error } = useQuery<SignalRow[]>({
    queryKey: ['signals', days, goldenOnly],
    queryFn: () =>
      fetch(`/api/signals?days=${days}&limit=100${goldenOnly ? '&golden=true' : ''}`).then(r =>
        r.json()
      ),
    staleTime: 60_000,
    refetchInterval: 60_000,
  })

  const filtered =
    filter === 'ALL'
      ? (data ?? [])
      : (data ?? []).filter(s => s.rise_category === filter)

  return (
    <div className="space-y-5">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-xl font-semibold text-[var(--color-text-1)]">시그널</h1>
          <p className="text-sm text-[var(--color-text-2)] mt-1">
            트리거 이벤트 — 상승 원인 카테고리별 분류
          </p>
        </div>

        {/* 기간 + 골든 필터 */}
        <div className="flex items-center gap-3">
          <select
            value={days}
            onChange={e => setDays(Number(e.target.value))}
            className="text-xs bg-[var(--color-surface)] border border-[var(--color-border)] rounded px-2 py-1.5 text-[var(--color-text-1)]"
          >
            <option value={7}>7일</option>
            <option value={30}>30일</option>
            <option value={90}>90일</option>
          </select>
          <button
            onClick={() => setGoldenOnly(v => !v)}
            className={`text-xs px-3 py-1.5 rounded border transition-colors ${
              goldenOnly
                ? 'bg-[var(--color-gold)]/20 border-[var(--color-gold)] text-[var(--color-gold)]'
                : 'border-[var(--color-border)] text-[var(--color-text-2)] hover:text-[var(--color-text-1)]'
            }`}
          >
            골든만
          </button>
        </div>
      </div>

      {/* 카테고리 필터 탭 */}
      <div className="flex flex-wrap gap-2">
        <button
          onClick={() => setFilter('ALL')}
          className={`text-xs px-3 py-1.5 rounded border transition-colors ${
            filter === 'ALL'
              ? 'bg-[var(--color-accent)]/20 border-[var(--color-accent)] text-[var(--color-accent)]'
              : 'border-[var(--color-border)] text-[var(--color-text-2)] hover:text-[var(--color-text-1)]'
          }`}
        >
          전체
        </button>
        {ALL_CATEGORIES.map(cat => {
          const meta = RISE_CATEGORY_META[cat]
          const active = filter === cat
          return (
            <button
              key={cat}
              onClick={() => setFilter(cat)}
              title={meta.desc}
              className={`text-xs px-3 py-1.5 rounded border transition-colors ${
                active
                  ? `${meta.bg} ${meta.color} border-current`
                  : 'border-[var(--color-border)] text-[var(--color-text-2)] hover:text-[var(--color-text-1)]'
              }`}
            >
              {meta.label}
            </button>
          )
        })}
      </div>

      {isLoading && (
        <div className="space-y-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="h-24 rounded-lg bg-[var(--color-surface)] animate-pulse" />
          ))}
        </div>
      )}

      {error && (
        <div className="rounded-lg bg-[var(--color-surface)] border border-[var(--color-error)] p-4 text-sm text-[var(--color-error)]">
          시그널 데이터를 불러오지 못했습니다.
        </div>
      )}

      {!isLoading && !error && filtered.length === 0 && (
        <div className="space-y-4">
          <div className="rounded-lg bg-[var(--color-surface)] border border-[var(--color-border)] p-8 text-center">
            <p className="text-sm text-[var(--color-text-2)]">
              {filter === 'ALL' ? '탐지된 시그널이 없습니다.' : `${RISE_CATEGORY_META[filter as RiseCategory]?.label} 시그널이 없습니다.`}
            </p>
            <p className="text-xs text-[var(--color-text-2)] mt-1">
              데이터 수집 파이프라인 실행 후 시그널이 나타납니다.
            </p>
          </div>

          {/* 카테고리 가이드 — 데이터 없을 때도 항상 표시 */}
          <CategoryGuide />
        </div>
      )}

      {filtered.length > 0 && (
        <div className="space-y-3">
          {filtered.map(signal => (
            <SignalCard key={signal.id} signal={signal} />
          ))}
          {/* 아래에 카테고리 가이드 */}
          <CategoryGuide />
        </div>
      )}
    </div>
  )
}

function SignalCard({ signal }: { signal: SignalRow }) {
  const name = signal.stocks?.name_kr || signal.stocks?.name_en
  return (
    <div className="rounded-lg bg-[var(--color-surface)] border border-[var(--color-border)] p-4">
      <div className="flex items-start justify-between gap-4">
        <div className="space-y-1.5 min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-base font-semibold text-[var(--color-text-1)]">
              {signal.ticker}
            </span>
            {name && (
              <span className="text-sm text-[var(--color-text-2)]">{name}</span>
            )}
            <span className="text-xs px-1.5 py-0.5 rounded bg-[var(--color-card)] text-[var(--color-accent)]">
              {signal.event_type}
            </span>
            {signal.golden && (
              <span className="text-xs px-1.5 py-0.5 rounded bg-[var(--color-gold)]/20 text-[var(--color-gold)]">
                골든
              </span>
            )}
            {signal.rise_category && (
              <RiseCategoryBadge category={signal.rise_category} />
            )}
          </div>
          <p className="text-sm text-[var(--color-text-2)] line-clamp-2">{signal.summary}</p>
          {signal.matched_keywords?.length > 0 && (
            <div className="flex flex-wrap gap-1">
              {signal.matched_keywords.slice(0, 5).map(kw => (
                <span
                  key={kw}
                  className="text-xs px-1 py-0.5 rounded bg-[var(--color-card)] text-[var(--color-text-2)]"
                >
                  {kw}
                </span>
              ))}
            </div>
          )}
        </div>

        <div className="text-right shrink-0">
          <div className="text-sm font-medium text-[var(--color-text-1)]">
            신뢰도 {Math.round((signal.confidence ?? 0) * 100)}%
          </div>
          <div className="text-xs text-[var(--color-text-2)] mt-0.5">
            {new Date(signal.detected_at).toLocaleDateString('ko-KR')}
          </div>
        </div>
      </div>
    </div>
  )
}

function CategoryGuide() {
  return (
    <div className="rounded-lg bg-[var(--color-surface)] border border-[var(--color-border)] p-4">
      <p className="text-sm font-medium text-[var(--color-text-1)] mb-3">상승 원인 카테고리 가이드</p>
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
        {ALL_CATEGORIES.map(cat => {
          const meta = RISE_CATEGORY_META[cat]
          return (
            <div key={cat} className="flex items-start gap-2">
              <span className={`mt-0.5 shrink-0 text-xs px-1.5 py-0.5 rounded font-medium ${meta.color} ${meta.bg}`}>
                {meta.label}
              </span>
              <p className="text-xs text-[var(--color-text-2)]">{meta.desc}</p>
            </div>
          )
        })}
      </div>
    </div>
  )
}
