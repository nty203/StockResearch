'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import {
  LayoutDashboard,
  TrendingUp,
  Zap,
  Inbox,
  Bookmark,
  Settings,
  FlaskConical,
  Target,
} from 'lucide-react'

const nav = [
  { href: '/',           label: '대시보드',    icon: LayoutDashboard },
  { href: '/hundredx',   label: '100배 시그널', icon: Target },
  { href: '/signals',    label: '시그널',      icon: Zap },
  { href: '/watchlist',  label: '워치리스트',  icon: Bookmark },
  { href: '/queue',      label: '분석 큐',     icon: Inbox },
  { href: '/backtest',   label: '백테스트',    icon: FlaskConical },
  { href: '/settings',   label: '설정',        icon: Settings },
]

export function Sidebar({
  isOpen = false,
  onClose,
}: {
  isOpen?: boolean
  onClose?: () => void
}) {
  const pathname = usePathname()

  return (
    <aside
      className={`
        fixed inset-y-0 left-0 z-40 w-64 bg-surface border-r border-border flex flex-col
        transform transition-transform duration-200 ease-out
        ${isOpen ? 'translate-x-0' : '-translate-x-full'}
        md:static md:translate-x-0 md:w-[200px] md:flex-shrink-0
      `}
    >
      <div className="px-4 py-5 border-b border-border flex items-center justify-between">
        <span className="text-lg font-bold text-text1">📈 10배</span>
      </div>
      <nav className="flex-1 py-2 overflow-y-auto">
        {nav.map(({ href, label, icon: Icon }) => {
          const active = href === '/' ? pathname === '/' : pathname.startsWith(href)
          return (
            <Link
              key={href}
              href={href}
              onClick={onClose}
              className={`flex items-center gap-3 px-4 py-3 text-sm transition-colors min-h-[44px] ${
                active
                  ? 'bg-card text-text1 font-medium'
                  : 'text-text2 hover:text-text1 hover:bg-card/50'
              }`}
            >
              <Icon size={16} />
              {label}
            </Link>
          )
        })}
      </nav>
    </aside>
  )
}
