'use client'
export const runtime = 'edge'

import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useParams } from 'next/navigation'
import type { ScreenScore, AgentScore, TriggerEvent, Stock } from '@stock/shared'

type Tab = 'overview' | 'events' | 'risk'

interface StockDetail {
  stock: Stock
  score: ScreenScore | null
  agentScores: AgentScore[]
  events: TriggerEvent[]
}

const SCORE_CATEGORIES = [
  { key: 'growth', label: 'Growth', max: 28 },
  { key: 'momentum', label: 'Momentum', max: 22 },
  { key: 'quality', label: 'Quality', max: 18 },
  { key: 'sponsorship', label: 'Sponsorship', max: 12 },
  { key: 'value', label: 'Value', max: 8 },
  { key: 'safety', label: 'Safety', max: 7 },
  { key: 'size', label: 'Size', max: 5 },
] as const

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

  const { stock, score, agentScores, events } = data

  return (
    <div className="space-y-6">
      {/* Hero */}
      <div className="rounded-lg bg-[var(--color-surface)] border border-[var(--color-border)] p-6">
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-3">
              <span className="text-2xl font-bold text-[var(--color-text-1)]">{ticker}</span>
              {stock.name_kr && (
                <span className="text-lg text-[var(--color-text-2)]">{stock.name_kr}</span>
              )}
              <span className="text-xs px-1.5 py-0.5 rounded bg-[var(--color-card)] text-[var(--color-text-2)]">
                {stock.market}
              </span>
            </div>
            {stock.sector_wics && (
              <p className="text-sm text-[var(--color-text-2)] mt-1">{stock.sector_wics}</p>
            )}
          </div>
          {score && (
            <div className="text-right shrink-0">
              <div className="text-3xl font-bold text-[var(--color-text-1)]">{Math.round(score.score_10x ?? 0)}</div>
              <div className="text-xs text-[var(--color-text-2)]">10X Score</div>
            </div>
          )}
        </div>
      </div>

      <div className="flex gap-6">
        {/* Main content with tabs */}
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
                {t === 'overview' ? '개요' : t === 'events' ? '이벤트' : '리스크'}
              </button>
            ))}
          </div>

          {tab === 'overview' && (
            <div className="rounded-lg bg-[var(--color-surface)] border border-[var(--color-border)] p-4">
              <p className="text-sm text-[var(--color-text-2)]">주가 차트는 Phase 5에서 구현됩니다.</p>
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
                        <div className="flex items-center gap-2">
                          <span className="text-xs px-1.5 py-0.5 rounded bg-[var(--color-card)] text-[var(--color-accent)]">
                            {ev.event_type}
                          </span>
                          {ev.golden && (
                            <span className="text-xs px-1.5 py-0.5 rounded bg-[var(--color-gold)]/20 text-[var(--color-gold)]">
                              골든
                            </span>
                          )}
                        </div>
                        <p className="text-sm text-[var(--color-text-2)] mt-1">{ev.summary}</p>
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
                const pct = val != null ? Math.round((val / cat.max) * 100) : 0
                return (
                  <div key={cat.key}>
                    <div className="flex justify-between text-xs text-[var(--color-text-2)] mb-0.5">
                      <span>{cat.label}</span>
                      <span>{val ?? '—'}</span>
                    </div>
                    <div className="h-1.5 rounded-full bg-[var(--color-card)]">
                      <div
                        className="h-1.5 rounded-full bg-[var(--color-accent)]"
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                  </div>
                )
              })}
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
