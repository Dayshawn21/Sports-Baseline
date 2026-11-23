import React from 'react'
import ReactDOM from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ReactQueryDevtools } from '@tanstack/react-query-devtools'
import App, { loadHomePage } from './App'
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

// Imported on demand: a static import put the home hooks' modules in the entry bundle (+8.4 KB gzip).
if (isHomeRoute(window.location.hash)) {
  void import('~/hooks/homePrefetch').then(({ prefetchHome }) => prefetchHome(queryClient, new Date()))
  void loadHomePage()
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
      <ReactQueryDevtools initialIsOpen={false} />
    </QueryClientProvider>
  </React.StrictMode>
)
