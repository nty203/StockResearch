'use client'
export const runtime = 'edge'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { RiseCategoryBadge, RISE_CATEGORY_META } from '@/components/ui/rise-category-badge'
import type { RiseCategory } from '@stock/shared'

const CATEGORIES = Object.keys(RISE_CATEGORY_META) as RiseCategory[]

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="block text-xs text-text2 mb-1">{label}</label>
      {children}
    </div>
  )
}

const inputCls = `
  w-full bg-surface border border-border rounded-lg px-3 py-2 text-sm text-text1
  placeholder:text-text2 focus:outline-none focus:border-[#60a5fa] transition-colors
`.trim()

export default function LibraryAddPage() {
  const router = useRouter()

  const [ticker, setTicker] = useState('')
  const [category, setCategory] = useState<RiseCategory>(CATEGORIES[0])
  const [riseStart, setRiseStart] = useState('')
  const [earliestSignal, setEarliestSignal] = useState('')
  const [peakMult, setPeakMult] = useState('')
  const [notes, setNotes] = useState('')

  const [status, setStatus] = useState<'idle' | 'loading' | 'ok' | 'error'>('idle')
  const [msg, setMsg] = useState('')

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!ticker.trim()) { setMsg('ticker를 입력하세요'); return }
    setStatus('loading')
    setMsg('')

    try {
      const res = await fetch('/api/hundredx/library/add', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ticker: ticker.trim(),
          category,
          rise_start_date: riseStart || null,
          earliest_signal_date: earliestSignal || null,
          peak_multiplier: peakMult ? parseFloat(peakMult) : null,
          notes: notes || null,
        }),
      })
      const json = await res.json()
      if (!res.ok) {
        setStatus('error')
        setMsg(json.error || '저장 실패')
      } else {
        setStatus('ok')
        setMsg(`${json.ticker} / ${json.category} 저장됨`)
        // Reset form
        setTicker(''); setRiseStart(''); setEarliestSignal(''); setPeakMult(''); setNotes('')
      }
    } catch (err) {
      setStatus('error')
      setMsg('네트워크 오류')
    }
  }

  return (
    <div className="p-4 md:p-6 max-w-lg mx-auto space-y-6">
      <div>
        <h1 className="text-xl font-bold text-text1">라이브러리 종목 추가</h1>
        <p className="text-sm text-text2 mt-1">
          100배 확인된 historical 종목을 수동으로 라이브러리에 등록합니다.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="bg-card border border-border rounded-xl p-5 space-y-4">
        <Field label="Ticker *">
          <input
            className={inputCls}
            placeholder="예: 012450  (stocks 테이블에 있어야 함)"
            value={ticker}
            onChange={e => setTicker(e.target.value.trim())}
          />
        </Field>

        <Field label="카테고리 *">
          <select
            className={inputCls}
            value={category}
            onChange={e => setCategory(e.target.value as RiseCategory)}
          >
            {CATEGORIES.map(cat => (
              <option key={cat} value={cat}>
                {RISE_CATEGORY_META[cat].label}
              </option>
            ))}
          </select>
          <div className="mt-1.5">
            <RiseCategoryBadge category={category} showDesc />
          </div>
        </Field>

        <div className="grid grid-cols-2 gap-3">
          <Field label="상승 시작일 (rise_start_date)">
            <input
              type="date"
              className={inputCls}
              value={riseStart}
              onChange={e => setRiseStart(e.target.value)}
            />
          </Field>
          <Field label="최초 신호일 (earliest_signal_date)">
            <input
              type="date"
              className={inputCls}
              value={earliestSignal}
              onChange={e => setEarliestSignal(e.target.value)}
            />
          </Field>
        </div>

        <Field label="Peak 배수 (peak_multiplier)">
          <input
            type="number"
            step="0.1"
            min="1"
            className={inputCls}
            placeholder="예: 12.5"
            value={peakMult}
            onChange={e => setPeakMult(e.target.value)}
          />
        </Field>

        <Field label="메모 (notes)">
          <textarea
            rows={3}
            className={`${inputCls} resize-none`}
            placeholder="상승 원인, 참고 자료, 특이사항 등"
            value={notes}
            onChange={e => setNotes(e.target.value)}
          />
        </Field>

        {msg && (
          <p className={`text-sm px-3 py-2 rounded-lg ${
            status === 'ok' ? 'bg-[#34d399]/10 text-[#34d399]' : 'bg-[#f87171]/10 text-[#f87171]'
          }`}>
            {msg}
          </p>
        )}

        <div className="flex gap-3 pt-1">
          <button
            type="submit"
            disabled={status === 'loading'}
            className="flex-1 bg-[#60a5fa] text-[#0a0a0f] font-medium text-sm rounded-lg py-2.5 hover:bg-[#60a5fa]/90 disabled:opacity-50 transition-colors"
          >
            {status === 'loading' ? '저장 중...' : '라이브러리에 추가'}
          </button>
          <button
            type="button"
            onClick={() => router.push('/library')}
            className="px-4 py-2.5 text-sm text-text2 hover:text-text1 hover:bg-card/50 rounded-lg transition-colors border border-border"
          >
            목록으로
          </button>
        </div>
      </form>

      <div className="text-xs text-text2 space-y-1">
        <p>• ticker는 <code className="bg-card px-1 rounded">stocks</code> 테이블에 등록된 종목코드여야 합니다</p>
        <p>• 같은 ticker + category 조합이 이미 있으면 덮어씁니다 (upsert)</p>
        <p>• 저장 후 자동으로 <code className="bg-card px-1 rounded">extract_signals</code>가 fingerprint를 채웁니다 (주 1회 실행)</p>
      </div>
    </div>
  )
}
