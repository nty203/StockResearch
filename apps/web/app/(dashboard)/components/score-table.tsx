'use client'

import { useQuery } from '@tanstack/react-query'
import Link from 'next/link'
import type { ScreenScore, RiseCategory } from '@stock/shared'
import { RiseCategoryBadge } from '@/components/ui/rise-category-badge'

type ScoreRow = ScreenScore & {
  name_kr?: string | null
  name_en?: string | null
  rise_category?: RiseCategory | null
}

export function ScoreTable() {
  const { data, isLoading } = useQuery<ScoreRow[]>({
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
        <>
          {/* Mobile card view */}
          <ul className="md:hidden divide-y divide-border/50">
            {data.map((row, i) => {
              const name = row.name_kr || row.name_en
              return (
                <li key={row.ticker}>
                  <Link
                    href={`/stocks/${row.ticker}`}
                    className="block px-4 py-3 hover:bg-card/50 transition-colors min-h-[44px]"
                  >
                    <div className="flex items-center justify-between gap-3 mb-1">
                      <div className="flex items-baseline gap-2 min-w-0">
                        <span className="text-text2 text-xs shrink-0">{i + 1}</span>
                        <span className="font-medium text-text1 text-sm truncate">
                          {name ?? row.ticker}
                        </span>
                        {name && (
                          <span className="text-text2 text-[11px] shrink-0">({row.ticker})</span>
                        )}
                      </div>
                      <div className="flex items-center gap-2 shrink-0">
                        <span className="font-semibold text-text1 text-base">
                          {row.score_10x.toFixed(0)}
                        </span>
                        <span className={row.passed ? 'text-success text-xs' : 'text-error text-xs'}>
                          {row.passed ? '✓' : '✗'}
                        </span>
                      </div>
                    </div>
                    <div className="flex items-center gap-2 text-[11px] text-text2 flex-wrap">
                      {row.rise_category && <RiseCategoryBadge category={row.rise_category} />}
                      <span>성장 {row.growth.toFixed(0)}</span>
                      <span>·</span>
                      <span>모멘텀 {row.momentum.toFixed(0)}</span>
                      <span>·</span>
                      <span>품질 {row.quality.toFixed(0)}</span>
                    </div>
                  </Link>
                </li>
              )
            })}
          </ul>

          {/* Desktop table view */}
          <div className="hidden md:block overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-border text-text2">
                  <th className="px-4 py-2 text-left w-4">#</th>
                  <th className="px-4 py-2 text-left">티커</th>
                  <th className="px-4 py-2 text-left">상승 원인</th>
                  <th className="px-4 py-2 text-right">10X점수</th>
                  <th className="px-4 py-2 text-right">성장성</th>
                  <th className="px-4 py-2 text-right">모멘텀</th>
                  <th className="px-4 py-2 text-right">품질</th>
                  <th className="px-4 py-2 text-right">통과</th>
                </tr>
              </thead>
              <tbody>
                {data.map((row, i) => {
                  const name = row.name_kr || row.name_en
                  return (
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
                          {name ? (
                            <>
                              <span className="font-medium text-text1">{name}</span>
                              <span className="text-text2 text-[11px] ml-1">({row.ticker})</span>
                            </>
                          ) : (
                            <span className="font-medium text-text1 text-xs">{row.ticker}</span>
                          )}
                        </Link>
                      </td>
                      <td className="px-4 py-2">
                        {row.rise_category ? (
                          <RiseCategoryBadge category={row.rise_category} />
                        ) : (
                          <span className="text-text2 text-[11px]">—</span>
                        )}
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
                  )
                })}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  )
}
