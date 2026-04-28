export const runtime = 'edge'

import { GoldenSignalFeed } from './components/golden-signal-feed'
import { WatchlistSummary } from './components/watchlist-summary'
import { ScoreTable } from './components/score-table'
import { SetupBanner } from './components/setup-banner'

export default function DashboardPage() {
  return (
    <div className="space-y-6">
      <SetupBanner />

      {/* Hero row: 골든 시그널 + 워치리스트 */}
      <div className="grid grid-cols-1 md:grid-cols-[1fr_200px] gap-4">
        <GoldenSignalFeed />
        <WatchlistSummary />
      </div>

      {/* 정량 스코어 상위 30 */}
      <ScoreTable />
    </div>
  )
}
