'use client'

import { useQuery } from '@tanstack/react-query'
import Link from 'next/link'
import type { ScreenScore } from '@stock/shared'

export function ScoreTable() {
  const { data, isLoading } = useQuery<ScreenScore[]>({
    queryKey: ['topScores'],
    queryFn: async () => {
      const res = await fetch('/api/scores?limit=30')
      if (!res.ok) return []
      return res.json()
    },
    staleTime: 30 * 60_000,
  })

  return (
    <div className="bg-surface border border-border rounded-lg">
      <div className="flex items-center justify-between px-4 py-3 border-b border-border">
        <h2 className="text-sm font-semibold text-text1">정량 스코어 상위 30</h2>
        <button className="text-xs text-accent hover:underline">새로고침</button>
      </div>

      {isLoading && (
        <div className="p-4 space-y-2">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="h-8 bg-card rounded animate-pulse" />
          ))}
        </div>
      )}

      {!isLoading && (!data || data.length === 0) && (
        <div className="py-8 text-center text-sm text-text2">
          스크리닝 결과 없음 — 필터 조정 또는{' '}
          <Link href="/settings" className="text-accent hover:underline">
            수집 재실행
          </Link>
        </div>
      )}

      {!isLoading && data && data.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-border text-text2">
                <th className="px-4 py-2 text-left w-4">#</th>
                <th className="px-4 py-2 text-left">티커</th>
                <th className="px-4 py-2 text-right">10X점수</th>
                <th className="px-4 py-2 text-right">Growth</th>
                <th className="px-4 py-2 text-right">Momentum</th>
                <th className="px-4 py-2 text-right">Quality</th>
                <th className="px-4 py-2 text-right">통과</th>
              </tr>
            </thead>
            <tbody>
              {data.map((row, i) => (
                <tr
                  key={row.ticker}
                  className="border-b border-border/50 hover:bg-card/50 transition-colors"
                >
                  <td className="px-4 py-2 text-text2">{i + 1}</td>
                  <td className="px-4 py-2">
                    <Link
                      href={`/stocks/${row.ticker}`}
                      className="hover:text-accent"
                    >
                      {(row as ScreenScore & { name_kr?: string }).name_kr && (
                        <span className="font-medium text-text1">
                          {(row as ScreenScore & { name_kr?: string }).name_kr}
                        </span>
                      )}
                      <span className={`text-text2 text-[11px] ${(row as ScreenScore & { name_kr?: string }).name_kr ? ' ml-1' : 'font-medium text-text1 text-xs'}`}>
                        {(row as ScreenScore & { name_kr?: string }).name_kr ? `(${row.ticker})` : row.ticker}
                      </span>
                    </Link>
                  </td>
                  <td className="px-4 py-2 text-right font-medium text-text1">
                    {row.score_10x.toFixed(0)}
                  </td>
                  <td className="px-4 py-2 text-right text-text2">{row.growth.toFixed(0)}</td>
                  <td className="px-4 py-2 text-right text-text2">{row.momentum.toFixed(0)}</td>
                  <td className="px-4 py-2 text-right text-text2">{row.quality.toFixed(0)}</td>
                  <td className="px-4 py-2 text-right">
                    <span className={row.passed ? 'text-success' : 'text-error'}>
                      {row.passed ? '✓' : '✗'}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
