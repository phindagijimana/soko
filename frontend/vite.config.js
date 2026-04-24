import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// GitHub project Pages: https://<user>.github.io/<repo>/
// In GitHub Actions, GITHUB_REPOSITORY is set and CI is true, so the client bundle loads from /<repo>/
const repo = process.env.GITHUB_REPOSITORY?.split('/')?.[1]
const base = process.env.VITE_BASE
  || (process.env.CI && repo ? `/${repo}/` : '/')

export default defineConfig({
  base,
  plugins: [react()],
  server: {
    // Listen on all interfaces (not only 127.0.0.1) so http://localhost:2000 works when
    // the OS resolves "localhost" to ::1, and so LAN/SSH port-forward can reach the dev server.
    host: true,
    port: 2000,
    // Fail fast if 2000 is taken; do not silently jump to another port (e.g. 5173).
    strictPort: true,
  },
})
