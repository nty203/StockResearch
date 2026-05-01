'use client'

import { Menu } from 'lucide-react'

export function Header({ onMenuClick }: { onMenuClick?: () => void }) {
  return (
    <header className="h-12 flex items-center justify-between px-3 md:px-6 bg-surface border-b border-border flex-shrink-0">
      <div className="flex items-center gap-2 md:gap-3">
        <button
          type="button"
          aria-label="메뉴 열기"
          onClick={onMenuClick}
          className="md:hidden p-2 -ml-2 text-text2 hover:text-text1"
        >
          <Menu size={20} />
        </button>
        <span className="text-sm font-semibold text-text1">100배 시그널</span>
      </div>
    </header>
  )
}
