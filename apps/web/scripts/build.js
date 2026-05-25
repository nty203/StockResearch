// CF Pages 빌드 진입점.
//
// 호출 경로:
//   1. pnpm build → 이 스크립트 실행 → npx @cloudflare/next-on-pages
//   2. next-on-pages → pnpm dlx vercel build → 내부에서 pnpm run build 재호출
//   3. 재호출 시 VERCEL=1이 set돼 있으므로 이 스크립트가 `next build`만 실행
//   4. vercel CLI가 build 산출물을 후처리 (이 단계에서 monorepo 경로 중복 버그 발생)
//
// Vercel CLI bug 우회:
//   vercel CLI가 manifest를 `${cwd}/apps/web/.next/routes-manifest.json`에서 찾는데
//   실제 경로는 `${cwd}/.next/routes-manifest.json`이라 ENOENT. cwd는 이미 apps/web.
//   → next build 직후 apps/web/apps/web/.next 심볼릭링크를 만들어 lookup을 충족.
//
// 이 우회는 vercel CLI / next-on-pages 패치 시 제거 가능.

const { execSync } = require('child_process')
const fs = require('fs')
const path = require('path')

if (process.env.VERCEL) {
  execSync('next build', { stdio: 'inherit' })

  // vercel CLI monorepo path-duplication workaround
  const cwd = process.cwd()
  const nestedDir = path.join(cwd, 'apps', 'web')
  const nestedNext = path.join(nestedDir, '.next')
  const realNext = path.join(cwd, '.next')

  if (!fs.existsSync(nestedNext) && fs.existsSync(realNext)) {
    fs.mkdirSync(nestedDir, { recursive: true })
    try {
      fs.symlinkSync(realNext, nestedNext, 'junction')
      console.log(`[build.js] symlinked ${nestedNext} → ${realNext}`)
    } catch (e) {
      // 심볼릭 링크 실패 시 디렉토리 복사로 폴백
      console.warn(`[build.js] symlink failed (${e.message}), copying instead`)
      fs.cpSync(realNext, nestedNext, { recursive: true })
    }
  }
} else {
  execSync('npx @cloudflare/next-on-pages', { stdio: 'inherit' })
}
