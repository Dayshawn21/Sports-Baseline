import { useEffect } from 'react'

/** Safari has no requestIdleCallback; this delay keeps the fetch clear of first paint there too. */
const FALLBACK_DELAY_MS = 2000

/** Fetches lazy chunks once the browser is idle, so their first open has nothing to wait for. Pass module-level loaders. */
export function usePreloadWhenIdle(...loaders: (() => Promise<unknown>)[]) {
  useEffect(() => {
    const run = () => loaders.forEach(load => void load())
    if ('requestIdleCallback' in window) {
      const id = window.requestIdleCallback(run, { timeout: FALLBACK_DELAY_MS * 2 })
      return () => window.cancelIdleCallback(id)
    }
    const timer = setTimeout(run, FALLBACK_DELAY_MS)
    return () => clearTimeout(timer)
  }, []) // Loaders are module-level constants, so once on mount is the intent.
}
