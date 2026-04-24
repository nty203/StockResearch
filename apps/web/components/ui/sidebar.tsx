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
} from 'lucide-react'

const nav = [
  { href: '/',           label: '대시보드',    icon: LayoutDashboard },
  { href: '/signals',    label: '시그널',      icon: Zap },
  { href: '/watchlist',  label: '워치리스트',  icon: Bookmark },
  { href: '/queue',      label: '분석 큐',     icon: Inbox },
  { href: '/settings',   label: '설정',        icon: Settings },
]

export function Sidebar() {
  const pathname = usePathname()

  return (
    <aside className="w-[200px] flex-shrink-0 bg-surface border-r border-border flex flex-col">
      <div className="px-4 py-5 border-b border-border">
        <span className="text-lg font-bold text-text1">📈 10배</span>
      </div>
      <nav className="flex-1 py-2">
        {nav.map(({ href, label, icon: Icon }) => {
          const active = href === '/' ? pathname === '/' : pathname.startsWith(href)
          return (
            <Link
              key={href}
              href={href}
              className={`flex items-center gap-3 px-4 py-2.5 text-sm transition-colors ${
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
