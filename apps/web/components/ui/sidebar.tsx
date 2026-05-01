'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { Target, BookOpen, BarChart2, PlusCircle } from 'lucide-react'

const nav = [
  { href: '/',               label: '100배 시그널', icon: Target },
  { href: '/library',        label: '라이브러리',   icon: BookOpen },
  { href: '/library/stats',  label: '카테고리 통계', icon: BarChart2 },
  { href: '/library/add',    label: '종목 추가',    icon: PlusCircle },
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
          // Exact-match for leaf paths; prefix for / and /hundredx alias
          const active =
            href === '/'
              ? pathname === '/' || pathname.startsWith('/hundredx')
              : href === '/library'
              ? pathname === '/library'
              : pathname === href
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
