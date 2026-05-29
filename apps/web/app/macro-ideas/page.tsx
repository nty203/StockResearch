'use client'
export const runtime = 'edge'

import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import type { MacroIdea } from '@stock/shared'
import { Globe, Home, ChevronDown, ChevronUp, AlertTriangle, Clock } from 'lucide-react'

interface MacroIdeasResponse {
  ideas: MacroIdea[]
  count: number
}

function ScoreBar({ label, score, max }: { label: string; score: number; max: number }) {
  const pct = Math.round((score / max) * 100)
  return (
    <div className="flex items-center gap-2 text-xs">
      <span className="w-28 shrink-0 text-zinc-400">{label}</span>
      <div className="flex-1 h-1.5 bg-zinc-800 rounded-full overflow-hidden">
        <div
          className="h-full rounded-full bg-blue-500"
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="w-10 text-right text-zinc-300 font-mono">{score}/{max}</span>
    </div>
  )
}

function ScoreGauge({ score }: { score: number }) {
  const color =
    score >= 80 ? 'text-emerald-400' :
    score >= 60 ? 'text-yellow-400' :
    'text-zinc-400'
  return (
    <div className={`text-3xl font-bold tabular-nums ${color}`}>
      {score}
      <span className="text-sm font-normal text-zinc-500">/100</span>
    </div>
  )
}

function PlayModeBadge({ mode }: { mode: MacroIdea['play_mode'] }) {
  if (mode === 'Global_Re_rating_Play') {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium bg-blue-900/50 text-blue-300 border border-blue-700/50">
        <Globe size={10} /> 글로벌 주도주
      </span>
    )
  }
  return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium bg-amber-900/50 text-amber-300 border border-amber-700/50">
      <Home size={10} /> 내수 대안주
    </span>
  )
}

function IdeaCard({ idea }: { idea: MacroIdea }) {
  const [expanded, setExpanded] = useState(false)

  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5 space-y-4">
      {/* Header */}
      <div className="flex items-start justify-between gap-3">
        <div className="space-y-1.5 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-xs text-zinc-500 font-mono">{idea.date}</span>
            <PlayModeBadge mode={idea.play_mode} />
          </div>
          <h2 className="text-base font-semibold text-zinc-100 leading-snug">{idea.title}</h2>
        </div>
        <ScoreGauge score={idea.total_score} />
      </div>

      {/* Score breakdown */}
      <div className="space-y-1.5">
        <ScoreBar label="현금흐름 직결성" score={idea.directness} max={30} />
        <ScoreBar label="이익 레버리지" score={idea.leverage} max={20} />
        <ScoreBar label="확장성·대안 매력" score={idea.scalability_or_rotation} max={30} />
        <ScoreBar label="수급·기술적 정렬" score={idea.technical_alignment} max={20} />
      </div>

      {/* Expand toggle */}
      <button
        onClick={() => setExpanded(v => !v)}
        className="flex items-center gap-1 text-xs text-zinc-500 hover:text-zinc-300 transition-colors"
      >
        {expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
        {expanded ? '접기' : '상세 보기'}
      </button>

      {expanded && (
        <div className="space-y-3 pt-1 border-t border-zinc-800">
          {idea.background && (
            <div>
              <p className="text-xs font-medium text-zinc-400 mb-1">배경</p>
              <p className="text-sm text-zinc-300 leading-relaxed">{idea.background}</p>
            </div>
          )}
          {idea.causal_chain && (
            <div>
              <p className="text-xs font-medium text-zinc-400 mb-1">인과관계</p>
              <p className="text-sm text-zinc-300 leading-relaxed">{idea.causal_chain}</p>
            </div>
          )}
          {/* Score rationales */}
          {(idea.directness_reason || idea.leverage_reason || idea.scalability_or_rotation_reason || idea.technical_alignment_reason) && (
            <div className="space-y-2">
              <p className="text-xs font-medium text-zinc-400">스코어링 근거</p>
              {idea.directness_reason && (
                <p className="text-xs text-zinc-400"><span className="text-zinc-500">직결성: </span>{idea.directness_reason}</p>
              )}
              {idea.leverage_reason && (
                <p className="text-xs text-zinc-400"><span className="text-zinc-500">레버리지: </span>{idea.leverage_reason}</p>
              )}
              {idea.scalability_or_rotation_reason && (
                <p className="text-xs text-zinc-400"><span className="text-zinc-500">확장성: </span>{idea.scalability_or_rotation_reason}</p>
              )}
              {idea.technical_alignment_reason && (
                <p className="text-xs text-zinc-400"><span className="text-zinc-500">수급: </span>{idea.technical_alignment_reason}</p>
              )}
            </div>
          )}
          {/* Strategic action */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {idea.market_timing && (
              <div className="bg-zinc-800/60 rounded-lg p-3 space-y-1">
                <div className="flex items-center gap-1 text-xs font-medium text-blue-400">
                  <Clock size={11} /> 진입 타이밍
                </div>
                <p className="text-xs text-zinc-300">{idea.market_timing}</p>
              </div>
            )}
            {idea.critical_risk && (
              <div className="bg-zinc-800/60 rounded-lg p-3 space-y-1">
                <div className="flex items-center gap-1 text-xs font-medium text-red-400">
                  <AlertTriangle size={11} /> 핵심 리스크
                </div>
                <p className="text-xs text-zinc-300">{idea.critical_risk}</p>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

export default function MacroIdeasPage() {
  const { data, isLoading, error } = useQuery<MacroIdeasResponse>({
    queryKey: ['macro-ideas'],
    queryFn: () => fetch('/api/macro-ideas?limit=20').then(r => r.json()),
  })

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-bold text-zinc-100">매크로 아이디어</h1>
        <p className="text-sm text-zinc-500 mt-0.5">
          정량 스크리닝 + 매크로 뉴스 기반 투자 가설 · 4축 100점 스코어링
        </p>
      </div>

      {isLoading && (
        <div className="text-sm text-zinc-500">로딩 중...</div>
      )}

      {error && (
        <div className="text-sm text-red-400">데이터를 불러올 수 없습니다.</div>
      )}

      {data && data.ideas.length === 0 && (
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-8 text-center">
          <p className="text-zinc-500 text-sm">아직 생성된 아이디어가 없습니다.</p>
          <p className="text-zinc-600 text-xs mt-1">Claude Code에서 <code className="text-zinc-400">/macro-idea</code>를 실행하여 첫 번째 가설을 생성하세요.</p>
        </div>
      )}

      {data && data.ideas.length > 0 && (
        <div className="space-y-4">
          <p className="text-xs text-zinc-600">총 {data.count}개 가설</p>
          {data.ideas.map(idea => (
            <IdeaCard key={idea.id} idea={idea} />
          ))}
        </div>
      )}
    </div>
  )
}
