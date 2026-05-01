// 메인 페이지는 100배 시그널 페이지와 동일.
// /hundredx URL alias 유지 (북마크 호환 + 롤백 안전).
'use client'
export const runtime = 'edge'

import HundredxPage from './hundredx/page'

export default HundredxPage
