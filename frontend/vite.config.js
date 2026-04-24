import { copyFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

const here = dirname(fileURLToPath(import.meta.url))

// GitHub project Pages: https://<user>.github.io/<repo>/
// In GitHub Actions, GITHUB_REPOSITORY is set and CI is true, so the client bundle loads from /<repo>/
const repo = process.env.GITHUB_REPOSITORY?.split('/')?.[1]
const base = process.env.VITE_BASE
  || (process.env.CI && repo ? `/${repo}/` : '/')

function spa404ForGitHubPages() {
  return {
    name: 'spa-github-pages-404',
    closeBundle() {
      const out = join(here, 'dist')
      copyFileSync(join(out, 'index.html'), join(out, '404.html'))
    },
  }
}

export default defineConfig({
  base,
  plugins: [react(), spa404ForGitHubPages()],
  server: {
    // Listen on all interfaces (not only 127.0.0.1) so http://localhost:2000 works when
    // the OS resolves "localhost" to ::1, and so LAN/SSH port-forward can reach the dev server.
    host: true,
    port: 2000,
    // Fail fast if 2000 is taken; do not silently jump to another port (e.g. 5173).
    strictPort: true,
  },
})
