import type { RiseCategory } from '@stock/shared'

export const RISE_CATEGORY_META: Record<RiseCategory, {
  label: string
  desc: string
  color: string
  bg: string
}> = {
  수주잔고_선행: {
    label: '수주잔고 선행',
    desc: '수주가 매출 반영보다 9~12개월 앞서 터짐 (방산/전력기기/조선)',
    color: 'text-[#60a5fa]',
    bg:    'bg-[#60a5fa]/15',
  },
  빅테크_파트너: {
    label: '빅테크 파트너십',
    desc: '대형 전략투자자 지분참여 + 콜옵션 구조 (로봇/반도체)',
    color: 'text-[#a78bfa]',
    bg:    'bg-[#a78bfa]/15',
  },
  임상_파이프라인: {
    label: '임상 파이프라인',
    desc: 'FDA/식약처 임상 단계 전환이 catalyst (바이오/제약)',
    color: 'text-[#34d399]',
    bg:    'bg-[#34d399]/15',
  },
  플랫폼_독점: {
    label: '플랫폼 독점',
    desc: '생태계 표준이 된 기술 플랫폼 — 학술·상업 채택률이 선행 신호',
    color: 'text-[#fb923c]',
    bg:    'bg-[#fb923c]/15',
  },
  정책_수혜: {
    label: '정책 수혜',
    desc: '정부 정책 전환(원전/방산 수출 확대)으로 수주 파이프라인 급팽창',
    color: 'text-[#fbbf24]',
    bg:    'bg-[#fbbf24]/15',
  },
  수익성_급전환: {
    label: '수익성 급전환',
    desc: '저마진 베이스에서 영업이익률이 급격히 반등하는 시점',
    color: 'text-[#f87171]',
    bg:    'bg-[#f87171]/15',
  },
  공급_병목: {
    label: '공급 병목',
    desc: '희소 소재/부품 공급 쇼티지 — 가격·수량 동시 급등 수혜',
    color: 'text-[#22d3ee]',
    bg:    'bg-[#22d3ee]/15',
  },
}

export function RiseCategoryBadge({ category, showDesc = false }: {
  category: RiseCategory
  showDesc?: boolean
}) {
  const meta = RISE_CATEGORY_META[category]
  if (!meta) return null
  return (
    <span
      title={meta.desc}
      className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium ${meta.color} ${meta.bg}`}
    >
      {meta.label}
      {showDesc && <span className="font-normal opacity-80 ml-1">{meta.desc}</span>}
    </span>
  )
}
