import path from 'path'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

const API_TARGET = process.env.VITE_API_URL || 'http://127.0.0.1:8000'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { '~': path.resolve(__dirname, 'src') },
  },
  server: {
    port: 3001,
    proxy: {
      '/api': { target: API_TARGET, changeOrigin: true, rewrite: (p) => p.replace(/^\/api/, '') },
      '/health': { target: API_TARGET, changeOrigin: true },
    },
  },
  build: { outDir: 'build' },
})
