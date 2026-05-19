'use client'
export const runtime = 'edge'

import { useEffect, useState, useCallback } from 'react'
import {
  CheckCircle,
  XCircle,
  Clock,
  Loader2,
  RefreshCw,
  AlertCircle,
  Calendar,
  GitBranch,
  Play,
  SkipForward,
  Minus,
} from 'lucide-react'

// ── Types ─────────────────────────────────────────────────────────────────────

type RunSummary = {
  id: number
  run_number: number
  status: string
  conclusion: string | null
  event: string
  created_at: string
  updated_at: string
}

type WorkflowStatus = {
  id: number
  name: string
  path: string
  state: string
  workflow_url: string
  last_run: (RunSummary & { run_url: string }) | null
  recent_runs: RunSummary[]
  fetch_error: string | null
}

type GithubActionsData = {
  repo: string
  fetched_at: string
  last_success_at: string | null
  workflows: WorkflowStatus[]
}

// ── Helpers ───────────────────────────────────────────────────────────────────

const WORKFLOW_LABELS: Record<string, string> = {
  'collect-daily.yml':          '데일리 수집',
  'collect-hourly.yml':         '시간별 수집',
  'collect-hundredx.yml':       '100배 스캐너',
  'collect-weekly.yml':         '주간 업데이트',
  'hundredx-auto-populate.yml': '100배 자동발굴 (월간)',
}

function wfLabel(path: string) {
  const filename = path.split('/').pop() ?? path
  return WORKFLOW_LABELS[filename] ?? filename
}

function formatKST(iso: string | null): string {
  if (!iso) return '—'
  const d = new Date(iso)
  return d.toLocaleString('ko-KR', {
    timeZone: 'Asia/Seoul',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function timeAgo(iso: string | null): string {
  if (!iso) return ''
  const diffMs = Date.now() - new Date(iso).getTime()
  const m = Math.floor(diffMs / 60_000)
  if (m < 1) return '방금 전'
  if (m < 60) return `${m}분 전`
  const h = Math.floor(m / 60)
  if (h < 24) return `${h}시간 전`
  const days = Math.floor(h / 24)
  return `${days}일 전`
}

// ── Status Badge ──────────────────────────────────────────────────────────────

function StatusBadge({ status, conclusion }: { status: string; conclusion: string | null }) {
  // in_progress / queued → running
  if (status === 'in_progress') {
    return (
      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-blue-500/20 text-blue-300 border border-blue-500/30">
        <Loader2 size={11} className="animate-spin" />
        실행 중
      </span>
    )
  }
  if (status === 'queued') {
    return (
      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-yellow-500/20 text-yellow-300 border border-yellow-500/30">
        <Clock size={11} />
        대기 중
      </span>
    )
  }
  // completed — check conclusion
  if (conclusion === 'success') {
    return (
      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
        <CheckCircle size={11} />
        성공
      </span>
    )
  }
  if (conclusion === 'failure') {
    return (
      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-red-500/20 text-red-400 border border-red-500/30">
        <XCircle size={11} />
        실패
      </span>
    )
  }
  if (conclusion === 'cancelled') {
    return (
      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-zinc-500/20 text-zinc-400 border border-zinc-500/30">
        <Minus size={11} />
        취소됨
      </span>
    )
  }
  if (conclusion === 'skipped') {
    return (
      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-zinc-500/20 text-zinc-400 border border-zinc-500/30">
        <SkipForward size={11} />
        스킵
      </span>
    )
  }
  return (
    <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-zinc-700/50 text-zinc-400 border border-zinc-600/30">
      <AlertCircle size={11} />
      {conclusion ?? status}
    </span>
  )
}

function EventBadge({ event }: { event: string }) {
  if (event === 'schedule') {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-medium bg-violet-500/15 text-violet-400">
        <Calendar size={9} />
        스케줄
      </span>
    )
  }
  if (event === 'workflow_dispatch') {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-medium bg-orange-500/15 text-orange-400">
        <Play size={9} />
        수동
      </span>
    )
  }
  return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-medium bg-zinc-700/50 text-zinc-500">
      <GitBranch size={9} />
      {event}
    </span>
  )
}

// ── Mini run history dots ─────────────────────────────────────────────────────

function RunDots({ runs }: { runs: RunSummary[] }) {
  return (
    <div className="flex items-center gap-1">
      {runs.map((r) => {
        const color =
          r.status === 'in_progress' ? 'bg-blue-400 animate-pulse' :
          r.status === 'queued'      ? 'bg-yellow-400' :
          r.conclusion === 'success' ? 'bg-emerald-400' :
          r.conclusion === 'failure' ? 'bg-red-400' :
          'bg-zinc-600'
        return (
          <span
            key={r.id}
            title={`#${r.run_number} ${r.conclusion ?? r.status} — ${formatKST(r.updated_at)}`}
            className={`w-2.5 h-2.5 rounded-full ${color}`}
          />
        )
      })}
    </div>
  )
}

// ── Workflow Card ─────────────────────────────────────────────────────────────

function WorkflowCard({ wf }: { wf: WorkflowStatus }) {
  const lr = wf.last_run

  return (
    <div className="bg-[#111318] border border-[#1e2029] rounded-xl p-5 flex flex-col gap-4 hover:border-[#2a2d3a] transition-colors">
      {/* Header */}
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <div className="text-sm font-semibold text-white truncate">{wfLabel(wf.path)}</div>
          <div className="text-[11px] text-zinc-500 mt-0.5 font-mono truncate">{wf.path.split('/').pop()}</div>
        </div>
        {lr ? (
          <StatusBadge status={lr.status} conclusion={lr.conclusion} />
        ) : (
          <span className="text-xs text-zinc-600">실행 기록 없음</span>
        )}
      </div>

      {/* Last run info */}
      {lr ? (
        <div className="flex flex-col gap-2">
          <div className="flex items-center justify-between text-xs">
            <div className="flex items-center gap-2 text-zinc-400">
              <Clock size={11} />
              <span>{formatKST(lr.updated_at)}</span>
              <span className="text-zinc-600">({timeAgo(lr.updated_at)})</span>
            </div>
            <EventBadge event={lr.event} />
          </div>

          {/* Recent run dots */}
          <div className="flex items-center gap-2">
            <span className="text-[10px] text-zinc-600">최근 5회</span>
            <RunDots runs={wf.recent_runs} />
          </div>
        </div>
      ) : null}

      {/* Error notice */}
      {wf.fetch_error && (
        <div className="text-[11px] text-red-400 bg-red-400/5 rounded px-2 py-1 border border-red-400/10">
          API 오류: {wf.fetch_error}
        </div>
      )}

      {/* Link */}
      {lr?.run_url && (
        <a
          href={lr.run_url}
          target="_blank"
          rel="noopener noreferrer"
          className="text-[11px] text-blue-400/70 hover:text-blue-400 transition-colors flex items-center gap-1 mt-auto"
        >
          GitHub에서 보기 →
        </a>
      )}
    </div>
  )
}

// ── Main Page ─────────────────────────────────────────────────────────────────

export default function SettingsPage() {
  const [data, setData] = useState<GithubActionsData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchData = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await fetch('/api/github-actions')
      if (!res.ok) throw new Error(`서버 오류: ${res.status}`)
      const json = await res.json() as GithubActionsData
      setData(json)
    } catch (e) {
      setError(e instanceof Error ? e.message : '알 수 없는 오류')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchData()
  }, [fetchData])

  const overallStatus = (() => {
    if (!data) return null
    const wfs = data.workflows
    const hasFailure = wfs.some(w => w.last_run?.conclusion === 'failure')
    const hasRunning = wfs.some(w => w.last_run?.status === 'in_progress' || w.last_run?.status === 'queued')
    const allSuccess = wfs.every(w => !w.last_run || w.last_run.conclusion === 'success' || w.last_run.conclusion === 'skipped')
    if (hasRunning) return 'running'
    if (hasFailure) return 'failure'
    if (allSuccess) return 'healthy'
    return 'partial'
  })()

  return (
    <div className="flex flex-col gap-6 p-4 md:p-6 max-w-4xl mx-auto w-full">
      {/* Page title */}
      <div className="flex items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-white">시스템 상태</h1>
          <p className="text-sm text-zinc-500 mt-0.5">GitHub Actions 자동화 파이프라인 모니터</p>
        </div>
        <button
          onClick={fetchData}
          disabled={loading}
          className="flex items-center gap-2 px-3 py-2 rounded-lg text-sm bg-[#1a1d26] hover:bg-[#22263a] border border-[#1e2029] text-zinc-300 transition-colors disabled:opacity-50"
        >
          <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
          새로고침
        </button>
      </div>

      {/* Global status banner */}
      {data && !loading && (
        <div
          className={`rounded-xl px-5 py-4 border flex flex-col sm:flex-row sm:items-center gap-3 ${
            overallStatus === 'healthy'  ? 'bg-emerald-500/10 border-emerald-500/25' :
            overallStatus === 'failure'  ? 'bg-red-500/10 border-red-500/25' :
            overallStatus === 'running'  ? 'bg-blue-500/10 border-blue-500/20' :
            'bg-yellow-500/10 border-yellow-500/20'
          }`}
        >
          <div className="flex items-center gap-3 flex-1">
            {overallStatus === 'healthy'  && <CheckCircle size={20} className="text-emerald-400 flex-shrink-0" />}
            {overallStatus === 'failure'  && <XCircle     size={20} className="text-red-400 flex-shrink-0" />}
            {overallStatus === 'running'  && <Loader2     size={20} className="text-blue-400 flex-shrink-0 animate-spin" />}
            {overallStatus === 'partial'  && <AlertCircle size={20} className="text-yellow-400 flex-shrink-0" />}
            <div>
              <div className={`font-semibold text-sm ${
                overallStatus === 'healthy' ? 'text-emerald-300' :
                overallStatus === 'failure' ? 'text-red-300' :
                overallStatus === 'running' ? 'text-blue-300' :
                'text-yellow-300'
              }`}>
                {overallStatus === 'healthy' ? '모든 워크플로우 정상' :
                 overallStatus === 'failure' ? '일부 워크플로우 실패' :
                 overallStatus === 'running' ? '워크플로우 실행 중' :
                 '일부 워크플로우 주의 필요'}
              </div>
              {data.last_success_at && (
                <div className="text-xs text-zinc-400 mt-0.5">
                  마지막 성공 업데이트: <span className="text-zinc-200 font-medium">{formatKST(data.last_success_at)}</span>
                  <span className="text-zinc-500 ml-1.5">({timeAgo(data.last_success_at)})</span>
                </div>
              )}
            </div>
          </div>

          {/* Repo link */}
          <a
            href={`https://github.com/${data.repo}/actions`}
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs text-blue-400/70 hover:text-blue-400 transition-colors whitespace-nowrap flex items-center gap-1"
          >
            <GitBranch size={12} />
            {data.repo}
          </a>
        </div>
      )}

      {/* Fetched at */}
      {data && (
        <div className="text-[11px] text-zinc-600 -mt-3">
          조회 시각: {formatKST(data.fetched_at)}
        </div>
      )}

      {/* Loading skeleton */}
      {loading && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="bg-[#111318] border border-[#1e2029] rounded-xl p-5 h-36 animate-pulse" />
          ))}
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="rounded-xl bg-red-500/10 border border-red-500/25 px-5 py-4 text-sm text-red-400 flex items-center gap-3">
          <XCircle size={16} />
          {error}
        </div>
      )}

      {/* Workflow cards */}
      {data && !loading && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {data.workflows.map((wf) => (
            <WorkflowCard key={wf.id} wf={wf} />
          ))}
        </div>
      )}

      {/* Legend */}
      {data && !loading && (
        <div className="border-t border-[#1e2029] pt-4">
          <p className="text-[11px] text-zinc-600 mb-2 font-medium">범례 — 최근 5회 실행</p>
          <div className="flex flex-wrap gap-3 text-[11px] text-zinc-500">
            <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-full bg-emerald-400 inline-block" /> 성공</span>
            <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-full bg-red-400 inline-block" /> 실패</span>
            <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-full bg-blue-400 inline-block" /> 실행 중</span>
            <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-full bg-yellow-400 inline-block" /> 대기</span>
            <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-full bg-zinc-600 inline-block" /> 취소/기타</span>
          </div>
        </div>
      )}
    </div>
  )
}
