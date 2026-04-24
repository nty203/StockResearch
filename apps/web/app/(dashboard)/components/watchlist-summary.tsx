'use client'

import { useQuery } from '@tanstack/react-query'
import Link from 'next/link'

interface WatchlistCounts {
  green: number
  yellow: number
  candidate: number
}

export function WatchlistSummary() {
  const { data, isLoading } = useQuery<WatchlistCounts>({
    queryKey: ['watchlistCounts'],
    queryFn: async () => {
      const res = await fetch('/api/watchlist/counts')
      if (!res.ok) return { green: 0, yellow: 0, candidate: 0 }
      return res.json()
    },
    refetchInterval: 5 * 60_000,
    staleTime: 5 * 60_000,
  })

  if (isLoading) {
    return <div className="bg-surface border border-border rounded-lg p-4 h-32 animate-pulse" />
  }

  return (
    <Link
      href="/watchlist"
      className="bg-surface border border-border rounded-lg p-4 flex flex-col gap-2 hover:border-accent/30 transition-colors"
    >
      <h2 className="text-sm font-semibold text-text1">워치리스트</h2>
      <div className="flex flex-col gap-1 text-sm">
        <div className="flex justify-between">
          <span className="text-success">Green</span>
          <span className="text-text1 font-medium">{data?.green ?? 0}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-warning">Yellow</span>
          <span className="text-text1 font-medium">{data?.yellow ?? 0}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-text2">후보</span>
          <span className="text-text2">{data?.candidate ?? 0}</span>
        </div>
      </div>
    </Link>
  )
}
