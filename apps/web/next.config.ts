import type { NextConfig } from 'next'

// outputFileTracingRoot는 의도적으로 설정하지 않음.
// CF Pages 빌드(next-on-pages → vercel build → next build)에서 이 옵션이 설정되면
// Vercel CLI가 manifest 경로에 apps/web을 중복으로 prepend해 ENOENT 발생.
// Next 15는 pnpm workspace를 자동 감지하므로 자동 트레이싱으로 충분.
const nextConfig: NextConfig = {
  // Cloudflare Pages compatibility
  // All route handlers must use export const runtime = 'edge'
}

export default nextConfig
