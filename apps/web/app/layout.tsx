export const runtime = 'edge'

import type { Metadata, Viewport } from 'next'
import './globals.css'
import { AppShell } from '@/components/ui/app-shell'
import { QueryProvider } from '@/components/ui/query-provider'

export const metadata: Metadata = {
  title: '10배 스크리너',
  description: '10배 상승주 조기 발굴 시스템',
}

export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko" className="dark">
      <body>
        <QueryProvider>
          <AppShell>{children}</AppShell>
        </QueryProvider>
      </body>
    </html>
  )
}
