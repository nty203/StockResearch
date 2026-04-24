'use client'

import { useQuery } from '@tanstack/react-query'
import Link from 'next/link'
import type { TriggerEvent } from '@stock/shared'

export function GoldenSignalFeed() {
  const { data, isLoading } = useQuery<TriggerEvent[]>({
    queryKey: ['goldenSignals'],
    queryFn: async () => {
      const res = await fetch('/api/signals?golden=true&days=7&limit=3')
      if (!res.ok) return []
      return res.json()
    },
    refetchInterval: 60_000,   // 1분 자동 갱신
    staleTime: 60_000,
  })

  return (
    <div className="bg-surface border border-border rounded-lg p-4">
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-sm font-semibold text-text1">골든 시그널 (7일)</h2>
        <Link href="/signals?filter=golden" className="text-xs text-accent hover:underline">
          전체 보기 →
        </Link>
      </div>

      {isLoading && <SkeletonCards />}

      {!isLoading && (!data || data.length === 0) && (
        <EmptyState />
      )}

      {!isLoading && data && data.length > 0 && (
        <div className="space-y-2">
          {data.map((signal) => (
            <SignalCard key={signal.id} signal={signal} />
          ))}
        </div>
      )}
    </div>
  )
}

function SignalCard({ signal }: { signal: TriggerEvent }) {
  return (
    <div className="bg-card border border-gold/20 rounded p-3 flex items-center justify-between">
      <div>
        <div className="flex items-center gap-2">
          <Link
            href={`/stocks/${signal.ticker}`}
            className="text-sm font-semibold text-text1 hover:text-accent"
          >
            {signal.ticker}
          </Link>
          <span className="text-xs text-text2">{signal.event_type}</span>
        </div>
        <p className="text-xs text-text2 mt-0.5 line-clamp-1">{signal.summary}</p>
      </div>
      <div className="flex items-center gap-3">
        <ConfidenceBar value={signal.confidence} />
        <AddToWatchlistButton ticker={signal.ticker} />
      </div>
    </div>
  )
}

function ConfidenceBar({ value }: { value: number }) {
  return (
    <div className="flex items-center gap-1.5">
      <div className="w-16 h-1.5 bg-border rounded-full">
        <div
          className="h-full bg-gold rounded-full"
          style={{ width: `${value}%` }}
        />
      </div>
      <span className="text-xs text-text2">{value}%</span>
    </div>
  )
}

function AddToWatchlistButton({ ticker }: { ticker: string }) {
  return (
    <button className="px-2 py-1 text-xs border border-border text-text2 rounded hover:border-accent hover:text-accent transition-colors">
      +워치리스트
    </button>
  )
}

function EmptyState() {
  return (
    <div className="text-center py-6 text-text2 text-sm">
      이번 주 골든 시그널 없음
      <br />
      <Link href="/signals" className="text-accent hover:underline text-xs">
        전체 시그널 보기
      </Link>
    </div>
  )
}

function SkeletonCards() {
  return (
    <div className="space-y-2">
      {[1, 2, 3].map((i) => (
        <div key={i} className="h-14 bg-card rounded animate-pulse" />
      ))}
    </div>
  )
}
