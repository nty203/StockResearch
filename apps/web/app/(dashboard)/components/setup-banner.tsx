'use client'

import { useQuery } from '@tanstack/react-query'

export function SetupBanner() {
  const { data: hasData } = useQuery<boolean>({
    queryKey: ['hasData'],
    queryFn: async () => {
      const res = await fetch('/api/pipeline/has-data')
      if (!res.ok) return false
      const { hasData } = await res.json()
      return hasData
    },
    staleTime: 60_000,
  })

  // 데이터가 있으면 배너 숨김
  if (hasData) return null
  // 로딩 중에도 숨김 (배너가 깜빡이지 않도록)
  if (hasData === undefined) return null

  return (
    <div className="bg-card border border-warning/30 rounded-lg p-4">
      <h3 className="text-sm font-semibold text-warning mb-3">
        첫 실행 — 데이터 수집이 필요합니다
      </h3>
      <div className="space-y-2 text-sm text-text2">
        <CheckItem label="Supabase 연결됨" done={true} />
        <CheckItem label="데이터 수집 실행 필요" done={false} />
      </div>
      <div className="mt-3 flex gap-2">
        <TriggerButton workflow="collect-daily.yml" label="지금 수집 실행" />
        <a href="/settings" className="text-xs text-accent hover:underline self-center">
          설정으로 이동 →
        </a>
      </div>
    </div>
  )
}

function CheckItem({ label, done }: { label: string; done: boolean }) {
  return (
    <div className="flex items-center gap-2">
      <span className={done ? 'text-success' : 'text-text2'}>
        {done ? '✓' : '○'}
      </span>
      <span>{label}</span>
    </div>
  )
}

function TriggerButton({ workflow, label }: { workflow: string; label: string }) {
  async function handleClick() {
    await fetch('/api/pipeline/trigger', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ workflow }),
    })
  }
  return (
    <button
      onClick={handleClick}
      className="px-3 py-1.5 bg-accent text-white text-xs rounded hover:bg-accent/80 transition-colors"
    >
      {label}
    </button>
  )
}
