import type { NextConfig } from 'next'
import path from 'path'

// Next 15에서 next.config.ts가 번들링되면서 __dirname이 원본 위치가 아닌 번들 위치를
// 가리켜 outputFileTracingRoot 계산이 어긋남(apps/web 중복). build 커맨드가
// `cd apps/web && pnpm build`이므로 process.cwd() = apps/web에서 한 단계 위가 repo root.
const repoRoot = path.resolve(process.cwd(), '..', '..')

const nextConfig: NextConfig = {
  // Cloudflare Pages compatibility
  // All route handlers must use export const runtime = 'edge'

  // pnpm monorepo: resolve symlinked node_modules from the repo root
  // Fixes "Could not find the module ... in the React Server Consumer Manifest"
  outputFileTracingRoot: repoRoot,
}

export default nextConfig
