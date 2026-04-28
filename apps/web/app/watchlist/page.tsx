'use client'
export const runtime = 'edge'

import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import Link from 'next/link'
import type { Watchlist } from '@stock/shared'

type WatchlistRow = Watchlist & { name_kr?: string | null; name_en?: string | null; score_10x?: number | null; percentile?: number | null }

const STATUS_TABS = ['green', 'yellow', 'candidate'] as const
type Tab = typeof STATUS_TABS[number]

const STATUS_LABELS: Record<Tab, string> = {
  green: 'Green',
  yellow: 'Yellow',
  candidate: '후보',
}

export default function WatchlistPage() {
  const [tab, setTab] = useState<Tab>('green')
  const queryClient = useQueryClient()

  const { data, isLoading } = useQuery<WatchlistRow[]>({
    queryKey: ['watchlist', tab],
    queryFn: () => fetch(`/api/watchlist?status=${tab}`).then(r => r.json()),
    staleTime: 5 * 60_000,
  })

  const promote = useMutation({
    mutationFn: ({ id, status }: { id: string; status: string }) =>
      fetch(`/api/watchlist/${id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status }),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['watchlist'] })
      queryClient.invalidateQueries({ queryKey: ['watchlist-counts'] })
    },
  })

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold text-[var(--color-text-1)]">워치리스트</h1>

      <div className="flex gap-1 border-b border-[var(--color-border)]">
        {STATUS_TABS.map(s => (
          <button
            key={s}
            onClick={() => setTab(s)}
            className={`px-4 py-2 text-sm font-medium transition-colors ${
              tab === s
                ? 'text-[var(--color-text-1)] border-b-2 border-[var(--color-accent)]'
                : 'text-[var(--color-text-2)] hover:text-[var(--color-text-1)]'
            }`}
          >
            {STATUS_LABELS[s]}
          </button>
        ))}
      </div>

      {isLoading && (
        <div className="space-y-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="h-28 rounded-lg bg-[var(--color-surface)] animate-pulse" />
          ))}
        </div>
      )}

      {!isLoading && (!data || data.length === 0) && (
        <div className="rounded-lg bg-[var(--color-surface)] border border-[var(--color-border)] p-8 text-center">
          <p className="text-sm text-[var(--color-text-2)]">{STATUS_LABELS[tab]} 종목이 없습니다.</p>
        </div>
      )}

      {data && data.length > 0 && (
        <div className="space-y-3">
          {data.map(item => (
            <div
              key={item.id}
              className="rounded-lg bg-[var(--color-surface)] border border-[var(--color-border)] p-4 space-y-3"
            >
              <div className="flex items-start justify-between gap-3 flex-wrap">
                <div className="flex-1 min-w-0">
                  <Link href={`/stocks/${item.ticker}`} className="hover:text-[var(--color-accent)]">
                    <span className="text-base font-semibold text-[var(--color-text-1)]">{item.ticker}</span>
                    {(item.name_kr || item.name_en) && (
                      <span className="text-sm text-[var(--color-text-2)] ml-2">{item.name_kr || item.name_en}</span>
                    )}
                  </Link>
                  <span className="text-xs text-[var(--color-text-2)] ml-2">
                    추가일 {new Date(item.added_at).toLocaleDateString('ko-KR')}
                  </span>
                </div>
                <div className="flex items-center gap-3 shrink-0">
                  {item.score_10x != null && (
                    <div className="text-right">
                      <div className="text-lg font-bold text-[var(--color-text-1)]">{Math.round(item.score_10x)}</div>
                      <div className="text-xs text-[var(--color-text-2)]">10X Score</div>
                    </div>
                  )}
                  {tab === 'candidate' && (
                    <button
                      onClick={() => promote.mutate({ id: item.id, status: 'yellow' })}
                      className="text-xs px-2 py-1 rounded bg-[var(--color-warning)]/20 text-[var(--color-warning)] hover:bg-[var(--color-warning)]/30"
                    >
                      Yellow로 승격
                    </button>
                  )}
                  {tab === 'yellow' && (
                    <button
                      onClick={() => promote.mutate({ id: item.id, status: 'green' })}
                      className="text-xs px-2 py-1 rounded bg-[var(--color-success)]/20 text-[var(--color-success)] hover:bg-[var(--color-success)]/30"
                    >
                      Green으로 승격
                    </button>
                  )}
                </div>
              </div>
              <div className="grid grid-cols-3 gap-2 sm:gap-4 text-xs sm:text-sm">
                <div>
                  <span className="text-[var(--color-text-2)]">목표가</span>
                  <p className="text-[var(--color-text-1)] font-medium">
                    {item.target_price ? item.target_price.toLocaleString() : '—'}
                  </p>
                </div>
                <div>
                  <span className="text-[var(--color-text-2)]">손절</span>
                  <p className="text-[var(--color-text-1)] font-medium">
                    {item.stop_loss ? item.stop_loss.toLocaleString() : '—'}
                  </p>
                </div>
                <div>
                  <span className="text-[var(--color-text-2)]">포지션</span>
                  <p className="text-[var(--color-text-1)] font-medium">
                    {item.position_size_plan ?? '—'}
                  </p>
                </div>
              </div>
              {item.notes && (
                <p className="text-sm text-[var(--color-text-2)]">{item.notes}</p>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
