import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
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
