'use client'
export const runtime = 'edge'

import { useQuery } from '@tanstack/react-query'
import type { TriggerEvent } from '@stock/shared'

interface SignalRow extends TriggerEvent {
  stocks?: { name_kr: string | null; name_en: string | null; market: string }
}

export default function SignalsPage() {
  const { data, isLoading, error } = useQuery<SignalRow[]>({
    queryKey: ['signals'],
    queryFn: () => fetch('/api/signals').then(r => r.json()),
    staleTime: 60_000,
    refetchInterval: 60_000,
  })

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-[var(--color-text-1)]">골든 시그널</h1>
        <p className="text-sm text-[var(--color-text-2)] mt-1">트리거 이벤트 전체 목록</p>
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

      {!isLoading && !error && (!data || data.length === 0) && (
        <div className="rounded-lg bg-[var(--color-surface)] border border-[var(--color-border)] p-8 text-center">
          <p className="text-sm text-[var(--color-text-2)]">탐지된 시그널이 없습니다.</p>
        </div>
      )}

      {data && data.length > 0 && (
        <div className="space-y-3">
          {data.map(signal => (
            <div
              key={signal.id}
              className="rounded-lg bg-[var(--color-surface)] border border-[var(--color-border)] p-4"
            >
              <div className="flex items-start justify-between gap-4">
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <span className="text-base font-semibold text-[var(--color-text-1)]">
                      {signal.ticker}
                    </span>
                    {signal.stocks?.name_kr && (
                      <span className="text-sm text-[var(--color-text-2)]">{signal.stocks.name_kr}</span>
                    )}
                    <span className="text-xs px-1.5 py-0.5 rounded bg-[var(--color-card)] text-[var(--color-accent)]">
                      {signal.event_type}
                    </span>
                    {signal.golden && (
                      <span className="text-xs px-1.5 py-0.5 rounded bg-[var(--color-gold)]/20 text-[var(--color-gold)]">
                        골든
                      </span>
                    )}
                  </div>
                  <p className="text-sm text-[var(--color-text-2)]">{signal.summary}</p>
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
          ))}
        </div>
      )}
    </div>
  )
}
