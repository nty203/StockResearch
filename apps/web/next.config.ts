import type { NextConfig } from 'next'
import path from 'path'

const nextConfig: NextConfig = {
  // Cloudflare Pages compatibility
  // All route handlers must use export const runtime = 'edge'

  // pnpm monorepo: resolve symlinked node_modules from the repo root
  // Fixes "Could not find the module ... in the React Server Consumer Manifest"
  outputFileTracingRoot: path.join(__dirname, '../../'),
}

export default nextConfig
