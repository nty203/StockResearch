'use client'
export const runtime = 'edge'

import { useState, useMemo, useEffect, useCallback, Suspense } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useRouter, useSearchParams } from 'next/navigation'
import Link from 'next/link'
import type { MacroIdea, MacroIdeaCandidate, MacroTheme } from '@stock/shared'
import { MACRO_THEMES } from '@stock/shared'
import { Globe, Home, AlertTriangle, Clock, TrendingUp, Search, X, BarChart2, SlidersHorizontal } from 'lucide-react'

type PlayFilter = 'all' | 'Global_Re_rating_Play' | 'Domestic_Alternative_Play'
type ScoreFilter = 0 | 60 | 70 | 80
type ThemeFilter = 'all' | MacroTheme

interface MacroIdeasResponse {
  ideas: MacroIdea[]
  count: number
}

interface DatesResponse {
  dates: { date: string; count: number }[]
}

function pctColor(v: number | null) {
  if (v == null) return 'text-zinc-500'
  if (v > 0) return 'text-emerald-400'
  if (v < 0) return 'text-red-400'
  return 'text-zinc-400'
}

function formatDateTab(dateStr: string) {
  const d = new Date(dateStr)
  const month = d.getUTCMonth() + 1
  const day = d.getUTCDate()
  return `${month}/${day}`
}

function ScoreBar({ label, score, max }: { label: string; score: number; max: number }) {
  const pct = Math.round((score / max) * 100)
  // Color based on pct
  const barColor = pct >= 80 ? 'bg-gradient-to-r from-emerald-500 to-teal-400' :
                   pct >= 60 ? 'bg-gradient-to-r from-amber-500 to-orange-400' :
                   'bg-gradient-to-r from-zinc-600 to-zinc-500'
  return (
    <div className="flex items-center gap-4 py-1.5 text-xs">
      <span className="w-28 shrink-0 text-zinc-400 font-medium">{label}</span>
      <div className="flex-1 h-2 bg-zinc-800/80 rounded-full overflow-hidden border border-zinc-700/30">
        <div className={`h-full rounded-full ${barColor} transition-all duration-500`} style={{ width: `${pct}%` }} />
      </div>
      <span className="w-12 text-right text-zinc-300 font-mono font-bold">{score}<span className="text-[10px] text-zinc-500">/{max}</span></span>
    </div>
  )
}

function ScoreGauge({ score, size = 'lg' }: { score: number; size?: 'sm' | 'lg' }) {
  const color =
    score >= 80 ? 'text-emerald-400' :
    score >= 60 ? 'text-amber-400' :
    'text-zinc-400'
  if (size === 'sm') {
    const bg =
      score >= 80 ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30' :
      score >= 60 ? 'bg-amber-500/20 text-amber-400 border border-amber-500/30' :
      'bg-zinc-800 text-zinc-400 border border-zinc-700'
    return (
      <span className={`shrink-0 inline-flex items-center justify-center w-8 h-8 rounded-lg text-xs font-bold ${bg}`}>
        {score}
      </span>
    )
  }

  // Circular gauge for LG
  const radius = 28
  const circumference = 2 * Math.PI * radius
  const strokeDashoffset = circumference - (score / 100) * circumference
  const strokeColor = score >= 80 ? 'stroke-emerald-400' : score >= 60 ? 'stroke-amber-400' : 'stroke-zinc-500'

  return (
    <div className="relative flex items-center justify-center shrink-0 w-20 h-20 bg-zinc-900 rounded-2xl border border-zinc-800 shadow-inner">
      <svg className="w-16 h-16 transform -rotate-90">
        <circle
          cx="32"
          cy="32"
          r={radius}
          className="stroke-zinc-800"
          strokeWidth="4"
          fill="transparent"
        />
        <circle
          cx="32"
          cy="32"
          r={radius}
          className={`${strokeColor} transition-all duration-700 ease-out`}
          strokeWidth="4"
          fill="transparent"
          strokeDasharray={circumference}
          strokeDashoffset={strokeDashoffset}
          strokeLinecap="round"
        />
      </svg>
      <div className="absolute flex flex-col items-center justify-center">
        <span className={`text-xl font-extrabold font-mono ${color}`}>{score}</span>
        <span className="text-[9px] text-zinc-500 font-medium -mt-1">SCORE</span>
      </div>
    </div>
  )
}

function PlayModeBadge({ mode, compact }: { mode: MacroIdea['play_mode']; compact?: boolean }) {
  if (mode === 'Global_Re_rating_Play') {
    return (
      <span className={`inline-flex items-center gap-1.5 rounded-full font-semibold bg-blue-500/10 text-blue-400 border border-blue-500/20 ${compact ? 'px-2 py-0.5 text-[10px]' : 'px-3 py-1 text-xs'}`}>
        <Globe size={compact ? 10 : 12} /> {compact ? '글로벌' : '글로벌 주도주'}
      </span>
    )
  }
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full font-semibold bg-amber-500/10 text-amber-400 border border-amber-500/20 ${compact ? 'px-2 py-0.5 text-[10px]' : 'px-3 py-1 text-xs'}`}>
      <Home size={compact ? 10 : 12} /> {compact ? '내수' : '내수 대안주'}
    </span>
  )
}

function CandidateTable({ candidates, withLinks }: { candidates: MacroIdeaCandidate[]; withLinks?: boolean }) {
  if (!candidates?.length) return null
  return (
    <div className="bg-zinc-900/40 rounded-xl border border-zinc-800 overflow-hidden">
      <div className="flex items-center gap-1.5 text-xs font-semibold text-emerald-400 px-4 py-3 border-b border-zinc-800 bg-zinc-900/60">
        <TrendingUp size={13} className="text-emerald-400" />
        수혜 후보 종목 <span className="text-zinc-500 font-normal text-[10px] ml-1">(모멘텀 기준 정렬)</span>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="text-zinc-500 border-b border-zinc-800 bg-zinc-950/40">
              <th className="text-left font-semibold py-2 px-4">종목</th>
              <th className="text-right font-semibold py-2 px-3 hidden sm:table-cell">52주高 대비</th>
              <th className="text-right font-semibold py-2 px-3">1M 수익률</th>
              <th className="text-right font-semibold py-2 px-3 hidden sm:table-cell">3M 수익률</th>
              <th className="text-right font-semibold py-2 px-4">종합 모멘텀</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-800/40">
            {candidates.map((c) => (
              <tr key={c.ticker} className="hover:bg-zinc-800/20 transition-colors">
                <td className="py-2.5 px-4">
                  <div className="flex items-center gap-2">
                    {withLinks ? (
                      <Link
                        href={`/stocks/${c.ticker}`}
                        className="font-semibold text-zinc-100 hover:text-blue-400 transition-colors"
                      >
                        {c.name ?? c.ticker}
                      </Link>
                    ) : (
                      <span className="font-semibold text-zinc-100">{c.name ?? c.ticker}</span>
                    )}
                    <span className="text-[10px] font-mono text-zinc-500 bg-zinc-800 px-1 py-0.5 rounded">{c.ticker}</span>
                    {c.role && <span className="text-zinc-400 text-[11px]">| {c.role}</span>}
                    {c.hundredx_match && (
                      <span className="px-1.5 py-0.5 rounded bg-violet-500/10 text-violet-400 text-[9px] font-semibold border border-violet-500/20">
                        {c.hundredx_match} 매칭
                      </span>
                    )}
                  </div>
                </td>
                <td className="text-right py-2.5 px-3 font-mono text-zinc-300 hidden sm:table-cell">
                  {c.near_52w_high != null ? `${c.near_52w_high.toFixed(1)}%` : '—'}
                </td>
                <td className={`text-right py-2.5 px-3 font-mono font-medium ${pctColor(c.ret_1m)}`}>
                  {c.ret_1m != null ? `${c.ret_1m > 0 ? '+' : ''}${c.ret_1m.toFixed(1)}%` : '—'}
                </td>
                <td className={`text-right py-2.5 px-3 font-mono font-medium hidden sm:table-cell ${pctColor(c.ret_3m)}`}>
                  {c.ret_3m != null ? `${c.ret_3m > 0 ? '+' : ''}${c.ret_3m.toFixed(1)}%` : '—'}
                </td>
                <td className="text-right py-2.5 px-4 font-mono font-bold text-zinc-100">
                  {c.momentum != null ? c.momentum.toFixed(0) : '—'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function DetailPanel({ idea }: { idea: MacroIdea | null }) {
  if (!idea) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-zinc-600 gap-3">
        <div className="p-4 bg-zinc-900 rounded-full border border-zinc-800">
          <BarChart2 size={32} className="text-zinc-500" />
        </div>
        <p className="text-sm">분석할 매크로 가설을 왼쪽 리스트에서 선택해 주세요.</p>
      </div>
    )
  }

  // Parse causal chain into blocks if it has separator arrows
  const causalChainSteps = idea.causal_chain
    ? idea.causal_chain.split(/\s*[-=]>\s*|\s*→\s*/).map(s => s.trim()).filter(Boolean)
    : []

  return (
    <div className="space-y-6 pb-8 max-w-4xl">
      {/* Header Card */}
      <div className="bg-gradient-to-br from-zinc-900 to-zinc-950 border border-zinc-800 rounded-2xl p-5 shadow-lg relative overflow-hidden">
        <div className="absolute top-0 right-0 w-32 h-32 bg-blue-500/5 rounded-full blur-3xl" />
        <div className="flex items-start justify-between gap-5 relative z-10">
          <div className="space-y-3 min-w-0 flex-1">
            <div className="flex items-center gap-2 flex-wrap">
              <PlayModeBadge mode={idea.play_mode} />
              {idea.theme && (
                <span className="px-2.5 py-0.5 rounded-full text-[10px] font-bold tracking-wider bg-violet-500/10 text-violet-400 border border-violet-500/20">
                  {idea.theme}
                </span>
              )}
              <span className="text-[11px] font-mono text-zinc-500 bg-zinc-800/80 px-2 py-0.5 rounded-full">{idea.date}</span>
            </div>
            <h2 className="text-xl font-extrabold text-zinc-100 leading-snug tracking-tight">{idea.title}</h2>
          </div>
          <ScoreGauge score={idea.total_score} />
        </div>
      </div>

      {/* Grid: Score breakdown & details */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Score breakdown card */}
        <div className="bg-zinc-900/80 rounded-xl p-5 border border-zinc-800/70 space-y-2">
          <h3 className="text-xs font-bold text-zinc-400 tracking-wider uppercase mb-2">가설 적합도 분석</h3>
          <ScoreBar label="현금흐름 직결성" score={idea.directness} max={30} />
          <ScoreBar label="이익 레버리지" score={idea.leverage} max={20} />
          <ScoreBar label="확장성·대안 매력" score={idea.scalability_or_rotation} max={30} />
          <ScoreBar label="수급·기술적 정렬" score={idea.technical_alignment} max={20} />
        </div>

        {/* Score rationales */}
        {(idea.directness_reason || idea.leverage_reason || idea.scalability_or_rotation_reason || idea.technical_alignment_reason) && (
          <div className="bg-zinc-900/80 rounded-xl p-5 border border-zinc-800/70 space-y-2.5">
            <h3 className="text-xs font-bold text-zinc-400 tracking-wider uppercase mb-1">스코어링 세부 판단 근거</h3>
            <div className="space-y-1.5 text-xs">
              {idea.directness_reason && (
                <p className="text-zinc-300 leading-normal"><span className="text-zinc-500 font-semibold">현금흐름:</span> {idea.directness_reason}</p>
              )}
              {idea.leverage_reason && (
                <p className="text-zinc-300 leading-normal"><span className="text-zinc-500 font-semibold">레버리지:</span> {idea.leverage_reason}</p>
              )}
              {idea.scalability_or_rotation_reason && (
                <p className="text-zinc-300 leading-normal"><span className="text-zinc-500 font-semibold">대안매력:</span> {idea.scalability_or_rotation_reason}</p>
              )}
              {idea.technical_alignment_reason && (
                <p className="text-zinc-300 leading-normal"><span className="text-zinc-500 font-semibold">기술수급:</span> {idea.technical_alignment_reason}</p>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Background Section */}
      {idea.background && (
        <div className="bg-zinc-900/30 rounded-xl p-5 border border-zinc-800/60">
          <h3 className="text-xs font-bold text-zinc-400 tracking-wider uppercase mb-2">거시 경제 배경 및 촉매</h3>
          <p className="text-sm text-zinc-300 leading-relaxed font-normal">{idea.background}</p>
        </div>
      )}

      {/* Visual Causal Chain Flow */}
      {causalChainSteps.length > 0 ? (
        <div className="bg-zinc-900/30 rounded-xl p-5 border border-zinc-800/60 space-y-3">
          <h3 className="text-xs font-bold text-zinc-400 tracking-wider uppercase">핵심 인과 체인 (Causal Chain)</h3>
          <div className="flex flex-col md:flex-row md:items-center gap-2 overflow-x-auto py-2">
            {causalChainSteps.map((step, idx) => (
              <div key={idx} className="flex flex-col md:flex-row md:items-center gap-2 shrink-0">
                <div className="bg-zinc-900 border border-zinc-800 px-3.5 py-2.5 rounded-lg text-xs font-medium text-zinc-200 hover:border-zinc-700 transition-colors shadow-sm">
                  <span className="text-[10px] text-blue-400 font-mono block mb-0.5">STEP 0{idx + 1}</span>
                  {step}
                </div>
                {idx < causalChainSteps.length - 1 && (
                  <div className="flex justify-center md:items-center text-zinc-600 font-mono text-sm py-1 md:py-0 px-2">
                    <span className="hidden md:inline">→</span>
                    <span className="inline md:hidden">↓</span>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      ) : idea.causal_chain ? (
        <div className="bg-zinc-900/30 rounded-xl p-5 border border-zinc-800/60 space-y-2">
          <h3 className="text-xs font-bold text-zinc-400 tracking-wider uppercase">핵심 인과 관계</h3>
          <p className="text-sm text-zinc-300 leading-relaxed">{idea.causal_chain}</p>
        </div>
      ) : null}

      {/* Candidate stocks table */}
      <CandidateTable candidates={idea.candidates ?? []} withLinks />

      {/* Timing + Risk Callouts */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {idea.market_timing && (
          <div className="bg-blue-500/5 rounded-xl p-5 border-l-4 border-blue-500 border-zinc-800/70 space-y-2">
            <div className="flex items-center gap-1.5 text-xs font-bold text-blue-400 uppercase tracking-wider">
              <Clock size={14} /> 진입 및 마켓 타이밍
            </div>
            <p className="text-xs text-zinc-300 leading-relaxed">{idea.market_timing}</p>
          </div>
        )}
        {idea.critical_risk && (
          <div className="bg-rose-500/5 rounded-xl p-5 border-l-4 border-rose-500 border-zinc-800/70 space-y-2">
            <div className="flex items-center gap-1.5 text-xs font-bold text-rose-400 uppercase tracking-wider">
              <AlertTriangle size={14} /> 핵심 모니터링 리스크
            </div>
            <p className="text-xs text-zinc-300 leading-relaxed">{idea.critical_risk}</p>
          </div>
        )}
      </div>
    </div>
  )
}

function SummaryBar({ ideas }: { ideas: MacroIdea[] }) {
  if (!ideas.length) return null
  const avg = Math.round(ideas.reduce((s, i) => s + i.total_score, 0) / ideas.length)
  const highCount = ideas.filter(i => i.total_score >= 80).length
  const themeCounts = MACRO_THEMES
    .map(t => ({ theme: t, count: ideas.filter(i => i.theme === t).length }))
    .filter(t => t.count > 0)
    .sort((a, b) => b.count - a.count)
    .slice(0, 5)

  return (
    <div className="flex items-center gap-4 md:gap-6 text-xs flex-wrap px-4 md:px-6 py-3 border-b border-zinc-800 bg-zinc-950">
      <div className="flex items-center gap-1.5">
        <BarChart2 size={12} className="text-zinc-500" />
        <span className="text-zinc-500">총</span>
        <span className="font-bold text-zinc-100">{ideas.length}개</span>
      </div>
      <div>
        <span className="text-zinc-500">평균</span>
        <span className={`ml-1 font-bold ${avg >= 70 ? 'text-emerald-400' : 'text-zinc-200'}`}>{avg}점</span>
      </div>
      {highCount > 0 && (
        <div>
          <span className="text-zinc-500">고확신(80+)</span>
          <span className="ml-1 font-bold text-emerald-400">{highCount}개</span>
        </div>
      )}
      {themeCounts.length > 0 && (
        <div className="flex items-center gap-1 flex-wrap">
          {themeCounts.map(({ theme, count }) => (
            <span key={theme} className="px-1.5 py-0.5 rounded bg-violet-900/30 text-violet-400 text-[10px] border border-violet-800/30">
              {theme} {count}
            </span>
          ))}
        </div>
      )}
    </div>
  )
}

function CompactCard({
  idea,
  isSelected,
  onClick,
}: {
  idea: MacroIdea
  isSelected: boolean
  onClick: () => void
}) {
  return (
    <button
      onClick={onClick}
      className={`w-full text-left px-3 py-2.5 rounded-lg border transition-all ${
        isSelected
          ? 'bg-blue-950/60 border-blue-600/70 border-l-[3px] border-l-blue-400'
          : 'bg-zinc-900 border-zinc-800 hover:border-zinc-700 hover:bg-zinc-800/50'
      }`}
    >
      <div className="flex items-center gap-2 mb-1.5">
        <ScoreGauge score={idea.total_score} size="sm" />
        <div className="min-w-0 flex-1 flex items-center gap-1.5 flex-wrap">
          <PlayModeBadge mode={idea.play_mode} compact />
          {idea.theme && (
            <span className="text-[10px] text-violet-400 truncate">{idea.theme}</span>
          )}
        </div>
      </div>
      <p className="text-xs font-medium text-zinc-200 line-clamp-2 leading-snug mb-0.5">{idea.title}</p>
      {idea.background && (
        <p className="text-[11px] text-zinc-600 line-clamp-1 leading-snug">{idea.background}</p>
      )}
    </button>
  )
}

const SCORE_OPTIONS: { label: string; value: ScoreFilter }[] = [
  { label: '전체', value: 0 },
  { label: '60+', value: 60 },
  { label: '70+', value: 70 },
  { label: '80+', value: 80 },
]

export default function MacroIdeasPage() {
  return (
    <Suspense fallback={<div className="p-6 text-sm text-zinc-500">로딩 중...</div>}>
      <MacroIdeasContent />
    </Suspense>
  )
}

function MacroIdeasContent() {
  const router = useRouter()
  const searchParams = useSearchParams()

  const [selectedDate, setSelectedDate] = useState<string | null>(null)
  const [playFilter, setPlayFilter] = useState<PlayFilter>('all')
  const [minScore, setMinScore] = useState<ScoreFilter>(0)
  const [themeFilter, setThemeFilter] = useState<ThemeFilter>('all')
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedId, setSelectedId] = useState<string | null>(searchParams.get('id'))
  const [mobileShowDetail, setMobileShowDetail] = useState(false)
  const [showFilters, setShowFilters] = useState(false)

  const { data: datesData, isLoading: datesLoading } = useQuery<DatesResponse>({
    queryKey: ['macro-ideas-dates'],
    queryFn: () => fetch('/api/macro-ideas/dates').then(r => r.json()),
  })

  const dates = datesData?.dates ?? []
  const activeDate = selectedDate ?? dates[0]?.date ?? null

  const { data, isLoading } = useQuery<MacroIdeasResponse>({
    queryKey: ['macro-ideas', activeDate],
    queryFn: () => {
      const url = activeDate
        ? `/api/macro-ideas?date=${activeDate}&limit=100`
        : '/api/macro-ideas?limit=100'
      return fetch(url).then(r => r.json())
    },
    enabled: !datesLoading,
  })

  const filteredIdeas = useMemo(() => {
    if (!data?.ideas) return []
    const q = searchQuery.trim().toLowerCase()
    return data.ideas.filter(idea => {
      if (playFilter !== 'all' && idea.play_mode !== playFilter) return false
      if (minScore > 0 && idea.total_score < minScore) return false
      if (themeFilter !== 'all' && idea.theme !== themeFilter) return false
      if (q) {
        const haystack = `${idea.title} ${idea.background ?? ''} ${idea.causal_chain ?? ''}`.toLowerCase()
        if (!haystack.includes(q)) return false
      }
      return true
    })
  }, [data?.ideas, playFilter, minScore, themeFilter, searchQuery])

  const selectedIdea = useMemo(
    () => filteredIdeas.find(i => i.id === selectedId) ?? filteredIdeas[0] ?? null,
    [filteredIdeas, selectedId]
  )

  const handleSelect = useCallback((idea: MacroIdea) => {
    setSelectedId(idea.id)
    router.replace(`?id=${idea.id}`, { scroll: false })
    setMobileShowDetail(true)
  }, [router])

  // Keyboard navigation
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (!filteredIdeas.length) return
      // Don't intercept when typing in search
      if ((e.target as HTMLElement).tagName === 'INPUT') return
      const idx = filteredIdeas.findIndex(i => i.id === selectedIdea?.id)
      if (e.key === 'ArrowDown') {
        e.preventDefault()
        const next = filteredIdeas[Math.min(idx + 1, filteredIdeas.length - 1)]
        if (next) handleSelect(next)
      } else if (e.key === 'ArrowUp') {
        e.preventDefault()
        const prev = filteredIdeas[Math.max(idx - 1, 0)]
        if (prev) handleSelect(prev)
      } else if (e.key === 'Escape') {
        setMobileShowDetail(false)
      }
    }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [filteredIdeas, selectedIdea, handleSelect])

  const allIdeas = data?.ideas ?? []
  const isEmpty = !isLoading && !datesLoading && allIdeas.length === 0

  return (
    // Negative margins cancel the main padding so we fill the full content area
    <div className="-mx-4 md:-mx-6 -my-4 md:-my-6 flex flex-col h-[calc(100vh-3.5rem)]">

      {/* Page header */}
      <div className="px-4 md:px-6 pt-4 md:pt-5 pb-3 border-b border-zinc-800 shrink-0">
        <h1 className="text-lg font-bold text-zinc-100">매크로 아이디어</h1>
        <p className="text-xs text-zinc-500 mt-0.5">정량 스크리닝 + 매크로 뉴스 기반 투자 가설 · 4축 100점 스코어링</p>
      </div>

      {/* Summary bar */}
      {allIdeas.length > 0 && <SummaryBar ideas={allIdeas} />}

      {/* Empty state */}
      {isEmpty && (
        <div className="flex flex-col items-center justify-center flex-1 text-center p-8">
          <p className="text-zinc-500 text-sm">아직 생성된 아이디어가 없습니다.</p>
          <p className="text-zinc-600 text-xs mt-1">
            Claude Code에서 <code className="text-zinc-400">/macro-idea</code>를 실행하여 첫 번째 가설을 생성하세요.
          </p>
        </div>
      )}

      {/* Loading */}
      {(isLoading || datesLoading) && !isEmpty && (
        <div className="flex items-center justify-center flex-1 text-sm text-zinc-500">로딩 중...</div>
      )}

      {/* Master-Detail layout */}
      {!isEmpty && !isLoading && !datesLoading && (
        <div className="flex flex-1 min-h-0">

          {/* LEFT: list panel */}
          <div className="w-full md:w-72 xl:w-80 shrink-0 md:border-r border-zinc-800 flex flex-col min-h-0">

            {/* Filters */}
            <div className="px-3 py-2.5 border-b border-zinc-800 space-y-2 shrink-0">
              {/* Top row: Date selector, search bar, filter toggle */}
              <div className="flex items-center gap-1.5">
                {/* Date Dropdown */}
                <select
                  value={activeDate ?? ''}
                  onChange={e => { setSelectedDate(e.target.value); setSelectedId(null) }}
                  className="w-20 bg-zinc-800 border border-zinc-700 rounded-md px-1 py-1.5 text-[11px] text-zinc-200 focus:outline-none focus:border-zinc-500 min-w-0"
                >
                  {dates.map(({ date, count }) => (
                    <option key={date} value={date}>
                      {formatDateTab(date)}
                    </option>
                  ))}
                </select>

                {/* Search Bar */}
                <div className="relative flex-1">
                  <Search size={11} className="absolute left-2 top-1/2 -translate-y-1/2 text-zinc-500 pointer-events-none" />
                  <input
                    type="text"
                    placeholder="검색..."
                    value={searchQuery}
                    onChange={e => setSearchQuery(e.target.value)}
                    className="w-full bg-zinc-800 border border-zinc-700 rounded-md pl-6 pr-6 py-1.5 text-xs text-zinc-200 placeholder-zinc-600 focus:outline-none focus:border-zinc-500"
                  />
                  {searchQuery && (
                    <button
                      onClick={() => setSearchQuery('')}
                      className="absolute right-2 top-1/2 -translate-y-1/2 text-zinc-500 hover:text-zinc-300"
                    >
                      <X size={11} />
                    </button>
                  )}
                </div>

                {/* Filter toggle button */}
                <button
                  onClick={() => setShowFilters(!showFilters)}
                  className={`p-1.5 border rounded-md transition-colors shrink-0 ${
                    showFilters || playFilter !== 'all' || minScore > 0 || themeFilter !== 'all'
                      ? 'bg-blue-950/80 text-blue-400 border-blue-800/80'
                      : 'bg-zinc-800 border-zinc-700 text-zinc-400 hover:text-zinc-200 hover:bg-zinc-700'
                  }`}
                  title="상세 필터"
                >
                  <SlidersHorizontal size={13} fill={showFilters ? "currentColor" : "none"} />
                </button>
              </div>

              {/* Expandable filters panel */}
              {showFilters && (
                <div className="pt-2 border-t border-zinc-800/60 space-y-2.5 animate-fadeIn">
                  {/* Play mode filter */}
                  <div>
                    <p className="text-[10px] text-zinc-500 font-medium mb-1">플레이 모드</p>
                    <div className="flex items-center gap-1">
                      {(['all', 'Global_Re_rating_Play', 'Domestic_Alternative_Play'] as PlayFilter[]).map(mode => (
                        <button
                          key={mode}
                          onClick={() => setPlayFilter(mode)}
                          className={`flex-1 px-1 py-1 rounded text-[10px] font-medium transition-colors ${
                            playFilter === mode
                              ? mode === 'all' ? 'bg-zinc-600 text-zinc-100'
                                : mode === 'Global_Re_rating_Play' ? 'bg-blue-800 text-blue-100'
                                : 'bg-amber-800 text-amber-100'
                              : 'bg-zinc-800 text-zinc-500 hover:text-zinc-300'
                          }`}
                        >
                          {mode === 'all' ? '전체' : mode === 'Global_Re_rating_Play' ? '글로벌' : '내수'}
                        </button>
                      ))}
                    </div>
                  </div>

                  {/* Score filter */}
                  <div>
                    <div className="flex items-center justify-between mb-1">
                      <p className="text-[10px] text-zinc-500 font-medium">최소 스코어</p>
                      <span className="text-[9px] text-zinc-600 font-mono">
                        {filteredIdeas.length}/{allIdeas.length}개 매칭
                      </span>
                    </div>
                    <div className="flex items-center gap-1">
                      {SCORE_OPTIONS.map(({ label, value }) => (
                        <button
                          key={value}
                          onClick={() => setMinScore(value)}
                          className={`flex-1 py-0.5 rounded text-[10px] font-medium transition-colors ${
                            minScore === value
                              ? 'bg-zinc-600 text-zinc-100'
                              : 'bg-zinc-800 border border-zinc-700 text-zinc-500 hover:text-zinc-300'
                          }`}
                        >
                          {label}
                        </button>
                      ))}
                    </div>
                  </div>

                  {/* Theme pills */}
                  <div>
                    <p className="text-[10px] text-zinc-500 font-medium mb-1">테마</p>
                    <div className="flex flex-wrap gap-1 max-h-24 overflow-y-auto pr-1">
                      <button
                        onClick={() => setThemeFilter('all')}
                        className={`px-2 py-0.5 rounded-full text-[10px] font-medium transition-colors ${
                          themeFilter === 'all' ? 'bg-zinc-600 text-zinc-100' : 'bg-zinc-800 border border-zinc-700 text-zinc-500 hover:text-zinc-300'
                        }`}
                      >
                        전체
                      </button>
                      {MACRO_THEMES.filter(t => allIdeas.some(i => i.theme === t)).map((theme: MacroTheme) => (
                        <button
                          key={theme}
                          onClick={() => setThemeFilter(themeFilter === theme ? 'all' : theme)}
                          className={`px-2 py-0.5 rounded-full text-[10px] font-medium transition-colors ${
                            themeFilter === theme
                              ? 'bg-violet-800 text-violet-100 border border-violet-600'
                              : 'bg-zinc-800 border border-zinc-700 text-zinc-500 hover:text-zinc-300'
                          }`}
                        >
                          {theme}
                        </button>
                      ))}
                    </div>
                  </div>
                </div>
              )}
            </div>

            {/* Card list */}
            <div className="flex-1 overflow-y-auto px-2 py-2 space-y-1.5">
              {filteredIdeas.length === 0 && (
                <p className="text-xs text-zinc-600 text-center py-6">필터 조건에 맞는 아이디어 없음</p>
              )}
              {filteredIdeas.map(idea => (
                <CompactCard
                  key={idea.id}
                  idea={idea}
                  isSelected={idea.id === selectedIdea?.id}
                  onClick={() => handleSelect(idea)}
                />
              ))}
            </div>
          </div>

          {/* RIGHT: detail panel (desktop) */}
          <div className="hidden md:block flex-1 overflow-y-auto px-6 py-5">
            <DetailPanel idea={selectedIdea} />
          </div>

          {/* Mobile: tappable "view detail" — card list stays, detail is overlay */}
          {mobileShowDetail && selectedIdea && (
            <div className="md:hidden fixed inset-0 z-50 bg-zinc-950 flex flex-col">
              <div className="flex items-center gap-3 px-4 py-3 border-b border-zinc-800 shrink-0">
                <button
                  onClick={() => setMobileShowDetail(false)}
                  className="text-xs text-zinc-400 hover:text-zinc-200 flex items-center gap-1"
                >
                  ← 목록
                </button>
                <span className="text-xs text-zinc-500 truncate">{selectedIdea.title}</span>
              </div>
              <div className="flex-1 overflow-y-auto px-4 py-4">
                <DetailPanel idea={selectedIdea} />
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
