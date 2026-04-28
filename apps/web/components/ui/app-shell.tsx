'use client'

import { useState, useEffect } from 'react'
import { usePathname } from 'next/navigation'
import { Sidebar } from './sidebar'
import { Header } from './header'

export function AppShell({ children }: { children: React.ReactNode }) {
  const [drawerOpen, setDrawerOpen] = useState(false)
  const pathname = usePathname()

  useEffect(() => {
    setDrawerOpen(false)
  }, [pathname])

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar isOpen={drawerOpen} onClose={() => setDrawerOpen(false)} />
      {drawerOpen && (
        <button
          aria-label="메뉴 닫기"
          onClick={() => setDrawerOpen(false)}
          className="fixed inset-0 bg-black/50 z-30 md:hidden"
        />
      )}
      <div className="flex flex-col flex-1 overflow-hidden">
        <Header onMenuClick={() => setDrawerOpen(v => !v)} />
        <main className="flex-1 overflow-auto p-4 md:p-6">
          {children}
        </main>
      </div>
    </div>
  )
}
