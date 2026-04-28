'use client'
export const runtime = 'edge'

import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import type { TriggerEvent, RiseCategory } from '@stock/shared'
import { RiseCategoryBadge, RISE_CATEGORY_META } from '@/components/ui/rise-category-badge'

interface SignalScore {
  score_10x: number | null
  passed: boolean
  growth: number
  momentum: number
  quality: number
  sponsorship: number
  scores_by_filter: Record<string, number> | null
}

interface SignalRow extends TriggerEvent {
  stocks?: { name_kr: string | null; name_en: string | null; market: string }
  score?: SignalScore | null
}

// 점수 기반 주요 카테고리 도출 (간이 버전 — signals 카드용)
function deriveScoreCategory(score: SignalScore): RiseCategory | null {
  const s = score.scores_by_filter
  if (!s) {
    // fallback: highest raw category
    const cats: [RiseCategory, number][] = [
      ['수주잔고_선행', score.growth],
      ['수익성_급전환', score.quality],
      ['빅테크_파트너', score.sponsorship],
      ['플랫폼_독점', score.momentum],
    ]
    const top = cats.sort((a, b) => b[1] - a[1])[0]
    return top[1] > 0 ? top[0] : null
  }
  const votes: [RiseCategory, number][] = [
    ['수주잔고_선행', (s['f13_bcr'] ?? 0) * 2.5 + (s['f14_backlog_growth'] ?? 0) * 2],
    ['수익성_급전환', (s['f15_opm_inflection'] ?? 0) * 3 + (s['f05_margin_trend'] ?? 0) * 1.5],
    ['플랫폼_독점', (s['f06_roic'] ?? 0) + (s['f05_op_margin'] ?? 0) + (s['f07_fcf'] ?? 0)],
    ['빅테크_파트너', (s['f10_foreign'] ?? 0) * 3 + (s['us10_institutional'] ?? 0) * 3],
  ]
  const top = votes.sort((a, b) => b[1] - a[1])[0]
  return top[1] > 0 ? top[0] : null
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
      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-[var(--color-text-1)]">시그널</h1>
          <p className="text-sm text-[var(--color-text-2)] mt-1">
            트리거 이벤트 — 상승 원인 카테고리별 분류
          </p>
        </div>

        {/* 기간 + 골든 필터 */}
        <div className="flex items-center gap-2 sm:gap-3 flex-wrap">
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
  const scoreCategory = signal.score?.passed ? deriveScoreCategory(signal.score) : null
  // 트리거 카테고리와 스코어 카테고리가 다르면 둘 다 표시
  const showScoreCat = scoreCategory && scoreCategory !== signal.rise_category

  return (
    <a href={`/stocks/${signal.ticker}`}
       className="block rounded-lg bg-[var(--color-surface)] border border-[var(--color-border)] p-4 hover:border-[var(--color-accent)]/50 transition-colors">
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
            {/* 트리거 기반 카테고리 */}
            {signal.rise_category && (
              <RiseCategoryBadge category={signal.rise_category} />
            )}
            {/* 스코어 기반 카테고리 (다를 때만) */}
            {showScoreCat && (
              <span className="text-[10px] text-[var(--color-text-2)] flex items-center gap-1">
                <span>정량↗</span>
                <RiseCategoryBadge category={scoreCategory} />
              </span>
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

        <div className="text-right shrink-0 space-y-1">
          <div className="text-sm font-medium text-[var(--color-text-1)]">
            신뢰도 {Math.round((signal.confidence ?? 0) * 100)}%
          </div>
          {signal.score?.score_10x != null && signal.score.passed && (
            <div className="text-xs font-medium text-[var(--color-accent)]">
              10X {Math.round(signal.score.score_10x)}점
            </div>
          )}
          <div className="text-xs text-[var(--color-text-2)]">
            {new Date(signal.detected_at).toLocaleDateString('ko-KR')}
          </div>
        </div>
      </div>
    </a>
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
