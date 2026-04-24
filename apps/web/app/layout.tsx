export const runtime = 'edge'

import type { Metadata } from 'next'
import './globals.css'
import { Sidebar } from '@/components/ui/sidebar'
import { Header } from '@/components/ui/header'
import { QueryProvider } from '@/components/ui/query-provider'

export const metadata: Metadata = {
  title: '10배 스크리너',
  description: '10배 상승주 조기 발굴 시스템',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko" className="dark">
      <body>
        <QueryProvider>
          <div className="flex h-screen overflow-hidden">
            <Sidebar />
            <div className="flex flex-col flex-1 overflow-hidden">
              <Header />
              <main className="flex-1 overflow-auto p-6">
                {children}
              </main>
            </div>
          </div>
        </QueryProvider>
      </body>
    </html>
  )
}
