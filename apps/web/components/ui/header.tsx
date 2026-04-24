'use client'

import { useQuery } from '@tanstack/react-query'

interface LastRun {
  stage: string
  ended_at: string | null
  status: string
}

function formatAge(isoDate: string | null): string {
  if (!isoDate) return '—'
  const diff = Date.now() - new Date(isoDate).getTime()
  const mins = Math.floor(diff / 60_000)
  if (mins < 60) return `${mins}분 전`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}시간 전`
  return `${Math.floor(hrs / 24)}일 전`
}

export function Header() {
  const { data } = useQuery<LastRun | null>({
    queryKey: ['lastRun'],
    queryFn: async () => {
      const res = await fetch('/api/pipeline/last-run')
      if (!res.ok) return null
      return res.json()
    },
    refetchInterval: 10_000,
    staleTime: 10_000,
  })

  return (
    <header className="h-12 flex items-center justify-between px-6 bg-surface border-b border-border flex-shrink-0">
      <div className="flex items-center gap-3">
        <MarketGateBadge market="KOSPI" />
        <MarketGateBadge market="S&P500" />
      </div>
      <div className="text-xs text-text2">
        {data
          ? `마지막 수집: ${formatAge(data.ended_at)}`
          : '수집 이력 없음'}
      </div>
    </header>
  )
}

function MarketGateBadge({ market }: { market: string }) {
  return (
    <span className="px-2 py-0.5 rounded text-xs bg-card border border-border text-text2">
      {market} <span className="text-text2">—</span>
    </span>
  )
}
