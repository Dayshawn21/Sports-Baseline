import path from 'path'
import { defineConfig, loadEnv, type Plugin } from 'vite'
import react from '@vitejs/plugin-react'
import { apiPreconnectTag } from './src/utils/apiPreconnect'

const API_TARGET = process.env.VITE_API_URL || 'http://127.0.0.1:8000'

/** Opens the API connection with the page; see `apiPreconnectTag`. */
function apiPreconnect(apiBaseUrl: string | undefined): Plugin {
  return {
    name: 'lineform-api-preconnect',
    transformIndexHtml() {
      const tag = apiPreconnectTag(apiBaseUrl)
      return tag ? [{ tag: 'link', attrs: { rel: 'preconnect', href: tag.href, crossorigin: '' }, injectTo: 'head-prepend' }] : []
    },
  }
}

export default defineConfig(({ mode }) => ({
  plugins: [react(), apiPreconnect(loadEnv(mode, process.cwd(), 'VITE_').VITE_API_BASE_URL)],
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
}))
