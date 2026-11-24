import React from 'react'
import ReactDOM from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ReactQueryDevtools } from '@tanstack/react-query-devtools'
import App, { preloadHomePage } from './App'
import { isHomeRoute } from '~/utils/homeRoute'
import './index.css'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000,
      gcTime: 10 * 60 * 1000,
      retry: 2,
      refetchOnWindowFocus: false,
    },
  },
})

function render() {
  ReactDOM.createRoot(document.getElementById('root')!).render(
    <React.StrictMode>
      <QueryClientProvider client={queryClient}>
        <App />
        <ReactQueryDevtools initialIsOpen={false} />
      </QueryClientProvider>
    </React.StrictMode>
  )
}

if (isHomeRoute(window.location.hash)) {
  // Imported on demand: a static import put the home hooks' modules in the entry bundle (+8.4 KB gzip).
  void import('~/hooks/homePrefetch').then(({ prefetchHome }) => prefetchHome(queryClient, new Date()))
  // A failed load still renders: the route's `lazy` fallback then retries and shows its error.
  preloadHomePage().catch(() => {}).finally(render)
} else {
  render()
}
