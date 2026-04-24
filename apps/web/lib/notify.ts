export const runtime = 'edge'

const BOT_TOKEN = process.env.TELEGRAM_BOT_TOKEN
const CHAT_ID = process.env.TELEGRAM_CHAT_ID

async function send(text: string) {
  if (!BOT_TOKEN || !CHAT_ID) return
  await fetch(`https://api.telegram.org/bot${BOT_TOKEN}/sendMessage`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ chat_id: CHAT_ID, text, parse_mode: 'Markdown' }),
  })
}

export async function alertGoldenSignal(ticker: string, triggerType: string, confidence: number) {
  await send(`🥇 *골든 시그널 탐지*\n종목: ${ticker}\n유형: ${triggerType}\n신뢰도: ${confidence}%`)
}

export async function alertWatchlistPromotion(ticker: string, from: string, to: string) {
  await send(`📈 *워치리스트 상태 변경*\n종목: ${ticker}\n${from} → ${to}`)
}

export async function alertPipelineFailure(stage: string, errorMsg: string, consecutiveFails: number) {
  if (consecutiveFails < 2) return
  await send(`⚠️ *파이프라인 실패 (${consecutiveFails}회 연속)*\n단계: ${stage}\n오류: ${errorMsg}`)
}

export async function alertQueueReset(count: number) {
  if (count === 0) return
  await send(`🔄 *큐 항목 자동 리셋*\n${count}개 항목이 48시간 타임아웃으로 PENDING 복귀됨`)
}
