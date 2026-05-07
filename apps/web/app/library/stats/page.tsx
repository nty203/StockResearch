'use client'
export const runtime = 'edge'

import { useQuery } from '@tanstack/react-query'
import { RiseCategoryBadge, RISE_CATEGORY_META } from '@/components/ui/rise-category-badge'
import type { RiseCategory } from '@stock/shared'

interface CategoryStat {
  category: string
  library_count: number
  library_peak_min: number | null
  library_peak_max: number | null
  library_peak_avg: number | null
  library_lead_months_avg: number | null
  active_matches: number
  avg_confidence: number | null
  fingerprint_matches: number
  exits_30d: number
}

interface StatsResponse {
  by_category: CategoryStat[]
  summary: {
    total_active: number
    total_library_stocks: number
    scan_coverage: number
    categories_firing: number
  }
}

function ConfBar({ value }: { value: number | null }) {
  if (value == null) return <span className="text-text2 text-xs">—</span>
  const pct = Math.round(value * 100)
  const color = pct >= 80 ? 'bg-[#34d399]' : pct >= 60 ? 'bg-[#fbbf24]' : 'bg-[#f87171]'
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 bg-border rounded-full overflow-hidden">
        <div className={`h-full ${color} rounded-full`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs text-text2 tabular-nums w-8 text-right">{pct}%</span>
    </div>
  )
}

function SummaryCard({ label, value, sub }: { label: string; value: string | number; sub?: string }) {
  return (
    <div className="bg-card rounded-lg border border-border p-4">
      <div className="text-xs text-text2 mb-1">{label}</div>
      <div className="text-2xl font-bold text-text1 tabular-nums">{value}</div>
      {sub && <div className="text-xs text-text2 mt-0.5">{sub}</div>}
    </div>
  )
}

export default function StatsPage() {
  const { data, isLoading, error } = useQuery<StatsResponse>({
    queryKey: ['hundredxStats'],
    queryFn: async () => {
      const res = await fetch('/api/hundredx/stats')
      if (!res.ok) throw new Error('stats fetch failed')
      return res.json()
    },
    staleTime: 5 * 60 * 1000,
  })

  if (isLoading) {
    return (
      <div className="p-6 max-w-5xl mx-auto">
        <div className="text-text2 text-sm">로딩 중...</div>
      </div>
    )
  }

  if (error || !data) {
    return (
      <div className="p-6 max-w-5xl mx-auto">
        <div className="text-[#f87171] text-sm">통계 로드 실패</div>
      </div>
    )
  }

  const { by_category, summary } = data

  return (
    <div className="p-4 md:p-6 max-w-5xl mx-auto space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-xl font-bold text-text1">카테고리 통계</h1>
        <p className="text-sm text-text2 mt-1">
          라이브러리 실적(ground truth) vs 현재 스캐너 결과 — 각 카테고리의 검출 근거와 신뢰도
        </p>
      </div>

      {/* Summary row */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <SummaryCard
          label="현재 활성 시그널"
          value={summary.total_active}
          sub={`${summary.categories_firing}개 카테고리 발화 중`}
        />
        <SummaryCard
          label="라이브러리 종목"
          value={summary.total_library_stocks}
          sub="100배 확인된 선례"
        />
        <SummaryCard
          label="스캔 대상"
          value={summary.scan_coverage.toLocaleString()}
          sub="활성 KR+US 종목"
        />
        <SummaryCard
          label="카테고리 수"
          value={by_category.length}
          sub="7개 패턴 탐지기"
        />
      </div>

      {/* Per-category table */}
      <div className="bg-card border border-border rounded-xl overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-text2 text-[10px] md:text-xs uppercase tracking-wider">
                <th className="text-left px-3 md:px-4 py-3 font-semibold">카테고리</th>
                <th className="text-center px-2 py-3 font-semibold">라이브러리<br/><span className="font-normal">선례</span></th>
                <th className="text-center px-2 py-3 font-semibold">최고 상승<br/><span className="font-normal">평균</span></th>
                <th className="hidden md:table-cell text-center px-3 py-3 font-semibold">평균 선행<br/><span className="font-normal">신호 리드</span></th>
                <th className="text-center px-2 py-3 font-semibold">현재 매칭<br/><span className="font-normal">활성</span></th>
                <th className="text-left px-3 md:px-4 py-3 font-semibold min-w-[100px] md:min-w-[120px]">평균 신뢰도</th>
                <th className="hidden lg:table-cell text-center px-3 py-3 font-semibold">핑거프린트<br/><span className="font-normal">매칭</span></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {by_category.map(stat => {
                const meta = RISE_CATEGORY_META[stat.category as RiseCategory]
                return (
                  <tr key={stat.category} className="hover:bg-surface transition-colors border-b border-border/50 last:border-0">
                    <td className="px-3 md:px-4 py-3">
                      <RiseCategoryBadge category={stat.category as RiseCategory} />
                      {meta && (
                        <p className="hidden md:block text-[11px] text-text2 mt-1 max-w-[220px] leading-relaxed italic">{meta.desc}</p>
                      )}
                    </td>
                    {/* Library count */}
                    <td className="px-2 py-3 text-center">
                      {stat.library_count > 0 ? (
                        <span className="text-text1 font-semibold">{stat.library_count}</span>
                      ) : (
                        <span className="text-text2">—</span>
                      )}
                    </td>
                    {/* Peak multiplier */}
                    <td className="px-2 py-3 text-center text-xs">
                      {stat.library_peak_avg != null ? (
                        <div className="flex flex-col items-center">
                          <span className="text-text1 font-bold">{stat.library_peak_avg.toFixed(0)}x</span>
                          {stat.library_peak_max != null && stat.library_peak_max !== stat.library_peak_avg && (
                            <span className="text-[10px] text-text2 tabular-nums">({stat.library_peak_max.toFixed(0)}x)</span>
                          )}
                        </div>
                      ) : (
                        <span className="text-text2">—</span>
                      )}
                    </td>
                    {/* Lead months */}
                    <td className="hidden md:table-cell px-3 py-3 text-center text-xs">
                      {stat.library_lead_months_avg != null ? (
                        <span className="text-text1">{stat.library_lead_months_avg}개월</span>
                      ) : (
                        <span className="text-text2">—</span>
                      )}
                    </td>
                    {/* Active matches */}
                    <td className="px-2 py-3 text-center">
                      {stat.active_matches > 0 ? (
                        <span className={`font-bold text-lg ${stat.active_matches >= 3 ? 'text-[#34d399]' : 'text-text1'}`}>
                          {stat.active_matches}
                        </span>
                      ) : (
                        <span className="text-text2 text-xs">0</span>
                      )}
                      {stat.exits_30d > 0 && (
                        <span className="block text-[10px] text-[#f87171] mt-0.5 font-medium">−{stat.exits_30d}</span>
                      )}
                    </td>
                    {/* Confidence bar */}
                    <td className="px-3 md:px-4 py-3">
                      {stat.active_matches > 0 ? (
                        <ConfBar value={stat.avg_confidence} />
                      ) : (
                        <span className="text-text2 text-xs">—</span>
                      )}
                    </td>
                    {/* Fingerprint matches */}
                    <td className="hidden lg:table-cell px-3 py-3 text-center text-xs">
                      {stat.active_matches > 0 ? (
                        <span className={stat.fingerprint_matches > 0 ? 'text-[#a78bfa] font-medium' : 'text-text2'}>
                          {stat.fingerprint_matches}/{stat.active_matches}
                        </span>
                      ) : (
                        <span className="text-text2">—</span>
                      )}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Legend */}
      <div className="bg-surface/50 border border-border/40 rounded-lg p-4 text-[11px] md:text-xs text-text2 space-y-2">
        <p className="flex items-start gap-2">
          <span className="w-1.5 h-1.5 rounded-full bg-text2 mt-1.5 shrink-0" />
          <span><strong className="text-text1">라이브러리 선례</strong> — 실제 100배 상승이 확인된 historical 종목 수 (ground truth)</span>
        </p>
        <p className="flex items-start gap-2">
          <span className="w-1.5 h-1.5 rounded-full bg-text2 mt-1.5 shrink-0" />
          <span><strong className="text-text1">평균 선행 신호 리드</strong> — earliest_signal_date → rise_start_date 사이 평균 개월 수</span>
        </p>
        <p className="flex items-start gap-2">
          <span className="w-1.5 h-1.5 rounded-full bg-text2 mt-1.5 shrink-0" />
          <span><strong className="text-text1">핑거프린트 매칭</strong> — 라이브러리 선례와 패턴 유사도 점수가 계산된 종목 비율</span>
        </p>
      </div>
    </div>
  )
}
