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
  build: {
    outDir: 'build',
    rollupOptions: {
      output: {
        // React and the router change only on upgrades, so a deploy of app code leaves this file cached.
        // Ant Design stays with Rollup's own splitting: one antd chunk would pull every page's
        // components (tables, forms, charts) into the first load.
        manualChunks(id) {
          if (/node_modules[\\/](react|react-dom|scheduler|react-router|react-router-dom)[\\/]/.test(id)) return 'react-vendor'
        },
      },
    },
  },
})
