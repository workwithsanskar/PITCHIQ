import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), 'VITE_')

  // A Vercel build without this value would make API requests go to the static
  // frontend origin, where the SPA fallback could return HTML instead of JSON.
  if (mode === 'production' && !env.VITE_API_BASE_URL?.trim()) {
    throw new Error('VITE_API_BASE_URL must be set for production builds.')
  }

  return {
    plugins: [react()],
    server: {
      port: 5173,
      proxy: { '/api': 'http://localhost:8000' },
    },
  }
})
