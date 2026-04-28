'use client'
export const runtime = 'edge'

import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import type { AnalysisQueue } from '@stock/shared'

type QueueGroup = { pending: AnalysisQueue[]; claimed: AnalysisQueue[]; completed: AnalysisQueue[] }

function hoursAgo(ts: string | null) {
  if (!ts) return 0
  return Math.floor((Date.now() - new Date(ts).getTime()) / 3_600_000)
}

export default function QueuePage() {
  const queryClient = useQueryClient()
  const [uploadId, setUploadId] = useState<string | null>(null)
  const [uploadText, setUploadText] = useState('')
  const [uploadError, setUploadError] = useState<string | null>(null)

  const { data, isLoading } = useQuery<QueueGroup>({
    queryKey: ['queue'],
    queryFn: () => fetch('/api/queue').then(r => r.json()),
    staleTime: 30_000,
    refetchInterval: 30_000,
  })

  const reset = useMutation({
    mutationFn: (id: string) =>
      fetch(`/api/queue/${id}/reset`, { method: 'POST' }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['queue'] }),
  })

  const upload = useMutation({
    mutationFn: ({ id, json }: { id: string; json: string }) =>
      fetch(`/api/queue/${id}/result`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: json,
      }).then(async r => {
        if (!r.ok) throw new Error(await r.text())
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['queue'] })
      setUploadId(null)
      setUploadText('')
      setUploadError(null)
    },
    onError: (e: Error) => setUploadError(e.message),
  })

  function handleUpload(id: string) {
    setUploadError(null)
    try {
      JSON.parse(uploadText)
    } catch {
      setUploadError('올바르지 않은 JSON 형식입니다.')
      return
    }
    upload.mutate({ id, json: uploadText })
  }

  const pending = data?.pending ?? [] as import('@stock/shared').AnalysisQueue[]
  const claimed = data?.claimed ?? [] as import('@stock/shared').AnalysisQueue[]
  const completed = data?.completed ?? [] as import('@stock/shared').AnalysisQueue[]

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-[var(--color-text-1)]">분석 큐</h1>
        <p className="text-sm text-[var(--color-text-2)] mt-1">에이전트 인박스 / 아웃박스</p>
      </div>

      {isLoading && (
        <div className="space-y-2">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="h-14 rounded bg-[var(--color-surface)] animate-pulse" />
          ))}
        </div>
      )}

      {!isLoading && pending.length === 0 && claimed.length === 0 && (
        <div className="rounded-lg bg-[var(--color-surface)] border border-[var(--color-border)] p-8 text-center">
          <p className="text-sm text-[var(--color-text-2)]">분석 큐가 비어있습니다.</p>
          <p className="text-xs text-[var(--color-text-2)] mt-1">점수 ≥ 65 종목이 없거나 아직 수집 전입니다.</p>
        </div>
      )}

      {pending.length > 0 && (
        <section className="space-y-2">
          <h2 className="text-xs font-medium text-[var(--color-text-2)] uppercase tracking-wider">
            PENDING ({pending.length})
          </h2>
          {pending.map(item => (
            <QueueRow
              key={item.id}
              item={item}
              onUploadClick={() => { setUploadId(item.id); setUploadText(''); setUploadError(null) }}
            />
          ))}
        </section>
      )}

      {claimed.length > 0 && (
        <section className="space-y-2">
          <h2 className="text-xs font-medium text-[var(--color-text-2)] uppercase tracking-wider">
            CLAIMED ({claimed.length})
          </h2>
          {claimed.map(item => {
            const h = hoursAgo(item.claimed_at)
            return (
              <div key={item.id} className="rounded bg-[var(--color-surface)] border border-[var(--color-border)] px-4 py-2.5 flex flex-wrap items-center gap-x-4 gap-y-2">
                <div className="flex-1 min-w-0">
                  <span className="text-sm font-medium text-[var(--color-text-1)]">{item.ticker}</span>
                  <span className="text-xs text-[var(--color-text-2)] ml-2">{item.prompt_type}</span>
                  {h >= 38 && (
                    <span className="ml-2 text-xs px-1.5 py-0.5 rounded bg-[var(--color-warning)]/20 text-[var(--color-warning)]">
                      ⚠ {h}h — 48h 내 완료 필요
                    </span>
                  )}
                </div>
                <div className="flex gap-2 flex-wrap shrink-0">
                  <button
                    onClick={() => { setUploadId(item.id); setUploadText(''); setUploadError(null) }}
                    className="text-xs px-2 py-1 rounded bg-[var(--color-accent)]/20 text-[var(--color-accent)]"
                  >
                    결과 업로드
                  </button>
                  <button
                    onClick={() => reset.mutate(item.id)}
                    className="text-xs px-2 py-1 rounded bg-[var(--color-card)] text-[var(--color-text-2)]"
                  >
                    강제 리셋
                  </button>
                </div>
              </div>
            )
          })}
        </section>
      )}

      {completed.length > 0 && (
        <details className="group">
          <summary className="text-xs font-medium text-[var(--color-text-2)] uppercase tracking-wider cursor-pointer list-none flex items-center gap-1">
            <span className="group-open:rotate-90 transition-transform inline-block">▶</span>
            COMPLETED ({completed.length})
          </summary>
          <div className="mt-2 space-y-2">
            {completed.slice(0, 10).map(item => (
              <div key={item.id} className="rounded bg-[var(--color-surface)] border border-[var(--color-border)] px-4 py-2 flex items-center gap-2">
                <span className="text-sm text-[var(--color-text-2)]">{item.ticker}</span>
                <span className="text-xs text-[var(--color-text-2)]">{item.prompt_type}</span>
                <span className="ml-auto text-xs text-[var(--color-success)]">완료</span>
              </div>
            ))}
          </div>
        </details>
      )}

      {uploadId && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4">
          <div className="bg-[var(--color-surface)] border border-[var(--color-border)] rounded-lg p-4 sm:p-6 w-full max-w-lg space-y-4">
            <h2 className="text-base font-semibold text-[var(--color-text-1)]">분석 결과 업로드</h2>
            <textarea
              value={uploadText}
              onChange={e => { setUploadText(e.target.value); setUploadError(null) }}
              placeholder={'{\n  "demand_score": 8,\n  "moat_score": 7,\n  "trigger_score": 9,\n  ...\n}'}
              rows={10}
              className="w-full rounded bg-[var(--color-card)] border border-[var(--color-border)] text-sm text-[var(--color-text-1)] p-3 font-mono resize-none focus:outline-none focus:border-[var(--color-accent)]"
            />
            {uploadError && (
              <p className="text-xs text-[var(--color-error)]">{uploadError}</p>
            )}
            <div className="flex gap-2 justify-end">
              <button
                onClick={() => { setUploadId(null); setUploadError(null) }}
                className="px-3 py-1.5 text-sm rounded bg-[var(--color-card)] text-[var(--color-text-2)]"
              >
                취소
              </button>
              <button
                onClick={() => handleUpload(uploadId)}
                disabled={upload.isPending}
                className="px-3 py-1.5 text-sm rounded bg-[var(--color-accent)] text-white disabled:opacity-50"
              >
                {upload.isPending ? '업로드 중...' : '업로드'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function QueueRow({ item, onUploadClick }: { item: AnalysisQueue; onUploadClick: () => void }) {
  return (
    <div className="rounded bg-[var(--color-surface)] border border-[var(--color-border)] px-4 py-2.5 flex flex-wrap items-center gap-x-4 gap-y-2">
      <div className="flex-1 min-w-0">
        <span className="text-sm font-medium text-[var(--color-text-1)]">{item.ticker}</span>
        <span className="text-xs text-[var(--color-text-2)] ml-2">{item.prompt_type}</span>
      </div>
      <div className="flex gap-2 flex-wrap shrink-0">
        {item.storage_path_prompt && (
          <a
            href={`/api/queue/${item.id}/download`}
            className="text-xs px-2 py-1 rounded bg-[var(--color-card)] text-[var(--color-text-2)]"
          >
            다운로드
          </a>
        )}
        <button
          onClick={onUploadClick}
          className="text-xs px-2 py-1 rounded bg-[var(--color-accent)]/20 text-[var(--color-accent)]"
        >
          결과 업로드
        </button>
      </div>
    </div>
  )
}
