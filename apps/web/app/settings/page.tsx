'use client'

import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import type { PipelineRun, Setting } from '@stock/shared'

const STAGES = ['universe', 'prices', 'financials', 'filings', 'news', 'scores', 'queue', 'notify'] as const
type Stage = typeof STAGES[number]

const STAGE_LABELS: Record<Stage, string> = {
  universe: '유니버스',
  prices: '가격',
  financials: '재무',
  filings: '공시',
  news: '뉴스',
  scores: '스코어',
  queue: '큐',
  notify: '알림',
}

const WORKFLOW_MAP: Record<Stage, string> = {
  universe: 'collect-daily.yml',
  prices: 'collect-hourly.yml',
  financials: 'collect-daily.yml',
  filings: 'collect-hourly.yml',
  news: 'collect-hourly.yml',
  scores: 'collect-daily.yml',
  queue: 'collect-daily.yml',
  notify: 'collect-daily.yml',
}

function timeAgo(ts: string): string {
  const diff = Math.floor((Date.now() - new Date(ts).getTime()) / 60_000)
  if (diff < 60) return `${diff}분 전`
  if (diff < 1440) return `${Math.floor(diff / 60)}시간 전`
  return `${Math.floor(diff / 1440)}일 전`
}

export default function SettingsPage() {
  const [section, setSection] = useState<'checklist' | 'schedule' | 'filters' | 'weights' | 'notify' | 'universe' | 'failures'>('checklist')
  const queryClient = useQueryClient()
  const [triggering, setTriggering] = useState<string | null>(null)

  const { data: runs } = useQuery<PipelineRun[]>({
    queryKey: ['pipeline-runs-latest'],
    queryFn: () => fetch('/api/pipeline/runs').then(r => r.json()),
    staleTime: 10_000,
    refetchInterval: 10_000,
  })

  const { data: settings } = useQuery<Setting[]>({
    queryKey: ['settings'],
    queryFn: () => fetch('/api/settings').then(r => r.json()),
    staleTime: 60_000,
  })

  const saveSettings = useMutation({
    mutationFn: (updates: { key: string; value_json: unknown }[]) =>
      fetch('/api/settings', {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(updates),
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['settings'] }),
  })

  async function triggerWorkflow(workflow: string) {
    setTriggering(workflow)
    try {
      await fetch('/api/pipeline/trigger', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ workflow }),
      })
    } finally {
      setTriggering(null)
      queryClient.invalidateQueries({ queryKey: ['pipeline-runs-latest'] })
    }
  }

  const latestByStage: Partial<Record<Stage, PipelineRun>> = {}
  for (const run of runs ?? []) {
    const stage = run.stage as Stage
    if (!latestByStage[stage]) latestByStage[stage] = run
  }

  const settingsMap: Record<string, unknown> = {}
  for (const s of settings ?? []) settingsMap[s.key] = s.value_json

  const SECTIONS = [
    { id: 'checklist', label: '업데이트 체크리스트' },
    { id: 'schedule', label: '스케줄 설정' },
    { id: 'filters', label: '필터 임계값' },
    { id: 'weights', label: '가중치 조정' },
    { id: 'notify', label: '알림 채널' },
    { id: 'universe', label: '유니버스 관리' },
    { id: 'failures', label: '실패 사례 학습' },
  ] as const

  return (
    <div className="flex gap-6">
      <nav className="w-48 shrink-0 space-y-1">
        {SECTIONS.map(s => (
          <button
            key={s.id}
            onClick={() => setSection(s.id)}
            className={`w-full text-left px-3 py-2 text-sm rounded transition-colors ${
              section === s.id
                ? 'bg-[var(--color-card)] text-[var(--color-text-1)]'
                : 'text-[var(--color-text-2)] hover:text-[var(--color-text-1)]'
            }`}
          >
            {s.label}
          </button>
        ))}
      </nav>

      <div className="flex-1 min-w-0">
        {section === 'checklist' && (
          <div className="space-y-4">
            <h2 className="text-base font-semibold text-[var(--color-text-1)]">업데이트 체크리스트</h2>
            <div className="rounded-lg border border-[var(--color-border)] divide-y divide-[var(--color-border)]">
              {STAGES.map(stage => {
                const run = latestByStage[stage]
                const ok = run?.status === 'success'
                const failed = run?.status === 'error'
                const workflow = WORKFLOW_MAP[stage]
                return (
                  <div key={stage} className="flex items-center gap-4 px-4 py-3">
                    <span className={`text-sm w-4 ${ok ? 'text-[var(--color-success)]' : failed ? 'text-[var(--color-error)]' : 'text-[var(--color-text-2)]'}`}>
                      {ok ? '✓' : failed ? '✗' : '—'}
                    </span>
                    <span className="text-sm text-[var(--color-text-1)] w-20">{STAGE_LABELS[stage]}</span>
                    <span className="text-sm text-[var(--color-text-2)] flex-1">
                      {run ? (ok ? timeAgo(run.ended_at ?? run.started_at) : failed ? '실패' : '실행 중') : '미실행'}
                    </span>
                    {run?.rows_processed != null && (
                      <span className="text-xs text-[var(--color-text-2)]">{run.rows_processed.toLocaleString()}행</span>
                    )}
                    <button
                      onClick={() => triggerWorkflow(workflow)}
                      disabled={triggering === workflow}
                      className="text-xs px-2 py-1 rounded bg-[var(--color-card)] text-[var(--color-accent)] hover:bg-[var(--color-border)] disabled:opacity-50"
                    >
                      {triggering === workflow ? '실행 중...' : '재실행'}
                    </button>
                  </div>
                )
              })}
            </div>
          </div>
        )}

        {section === 'filters' && (
          <FilterSettings settingsMap={settingsMap} onSave={v => saveSettings.mutate([v])} saving={saveSettings.isPending} />
        )}

        {section === 'weights' && (
          <WeightSettings settingsMap={settingsMap} onSave={v => saveSettings.mutate([v])} saving={saveSettings.isPending} />
        )}

        {section !== 'checklist' && section !== 'filters' && section !== 'weights' && (
          <div className="rounded-lg bg-[var(--color-surface)] border border-[var(--color-border)] p-8 text-center">
            <p className="text-sm text-[var(--color-text-2)]">준비 중입니다.</p>
          </div>
        )}
      </div>
    </div>
  )
}

function FilterSettings({
  settingsMap,
  onSave,
  saving,
}: {
  settingsMap: Record<string, unknown>
  onSave: (v: { key: string; value_json: unknown }) => void
  saving: boolean
}) {
  const threshold = (settingsMap['enqueue_score_threshold'] as number) ?? 65

  return (
    <div className="space-y-4">
      <h2 className="text-base font-semibold text-[var(--color-text-1)]">필터 임계값</h2>
      <div className="rounded-lg border border-[var(--color-border)] p-4 space-y-4">
        <div className="flex items-center gap-4">
          <label className="text-sm text-[var(--color-text-2)] w-40">에이전트 큐 진입 점수</label>
          <input
            type="number"
            defaultValue={threshold}
            min={0}
            max={100}
            className="w-20 rounded bg-[var(--color-card)] border border-[var(--color-border)] text-sm text-[var(--color-text-1)] px-2 py-1 focus:outline-none focus:border-[var(--color-accent)]"
            onBlur={e => onSave({ key: 'enqueue_score_threshold', value_json: Number(e.target.value) })}
          />
          <span className="text-xs text-[var(--color-text-2)]">기본값: 65</span>
        </div>
      </div>
      {saving && <p className="text-xs text-[var(--color-text-2)]">저장 중...</p>}
    </div>
  )
}

function WeightSettings({
  settingsMap,
  onSave,
  saving,
}: {
  settingsMap: Record<string, unknown>
  onSave: (v: { key: string; value_json: unknown }) => void
  saving: boolean
}) {
  const defaultWeights = { growth: 28, momentum: 22, quality: 18, sponsorship: 12, value: 8, safety: 7, size: 5 }
  const weights = (settingsMap['score_weights'] as typeof defaultWeights) ?? defaultWeights

  return (
    <div className="space-y-4">
      <h2 className="text-base font-semibold text-[var(--color-text-1)]">가중치 조정</h2>
      <div className="rounded-lg border border-[var(--color-border)] p-4 space-y-3">
        {(Object.keys(weights) as (keyof typeof defaultWeights)[]).map(k => (
          <div key={k} className="flex items-center gap-4">
            <label className="text-sm text-[var(--color-text-2)] w-28 capitalize">{k}</label>
            <input
              type="range"
              min={0}
              max={50}
              defaultValue={weights[k]}
              className="flex-1"
              onMouseUp={e => {
                const val = Number((e.target as HTMLInputElement).value)
                onSave({ key: 'score_weights', value_json: { ...weights, [k]: val } })
              }}
            />
            <span className="text-sm text-[var(--color-text-1)] w-6 text-right">{weights[k]}</span>
          </div>
        ))}
      </div>
      {saving && <p className="text-xs text-[var(--color-text-2)]">저장 중...</p>}
    </div>
  )
}
