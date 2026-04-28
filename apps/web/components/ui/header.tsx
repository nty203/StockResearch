'use client'

import { useQuery } from '@tanstack/react-query'
import { Menu } from 'lucide-react'

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

export function Header({ onMenuClick }: { onMenuClick?: () => void }) {
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
    <header className="h-12 flex items-center justify-between px-3 md:px-6 bg-surface border-b border-border flex-shrink-0">
      <div className="flex items-center gap-2 md:gap-3">
        <button
          type="button"
          aria-label="메뉴 열기"
          onClick={onMenuClick}
          className="md:hidden p-2 -ml-2 text-text2 hover:text-text1"
        >
          <Menu size={20} />
        </button>
        <MarketGateBadge market="KOSPI" short="KR" />
        <MarketGateBadge market="S&P500" short="US" />
      </div>
      <div className="hidden sm:block text-xs text-text2">
        {data
          ? `마지막 수집: ${formatAge(data.ended_at)}`
          : '수집 이력 없음'}
      </div>
    </header>
  )
}

function MarketGateBadge({ market, short }: { market: string; short: string }) {
  return (
    <span className="px-2 py-0.5 rounded text-xs bg-card border border-border text-text2">
      <span className="hidden sm:inline">{market}</span>
      <span className="sm:hidden">{short}</span>
      <span className="text-text2"> —</span>
    </span>
  )
}
