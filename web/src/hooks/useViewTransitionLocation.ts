import { useLayoutEffect, useRef, useState } from 'react'
import { flushSync } from 'react-dom'
import { useLocation, useNavigationType, type Location } from 'react-router-dom'
import { usePrefersReducedMotion } from '~/hooks/usePrefersReducedMotion'
import { shouldViewTransition, viewTransitionsSupported } from '~/utils/viewTransition'

/**
 * The location `<Routes>` renders. HashRouter has no `viewTransition` prop, so a page change
 * between sport pages is moved forward inside `document.startViewTransition` here instead.
 */
export function useViewTransitionLocation(): Location {
  const location = useLocation()
  const navigationType = useNavigationType()
  const reducedMotion = usePrefersReducedMotion()
  const [shown, setShown] = useState(location)
  const latest = useRef(location)
  const running = useRef<ViewTransition | null>(null)

  useLayoutEffect(() => {
    latest.current = location
    // A new navigation cuts the running fade short instead of queuing behind it.
    running.current?.skipTransition()
    running.current = null
    const fade = shouldViewTransition({
      from: shown.pathname,
      to: location.pathname,
      navigationType,
      supported: viewTransitionsSupported(document),
      reducedMotion,
    })
    if (!fade) {
      setShown(location)
      return
    }
    // A skipped transition still runs its callback later, so every callback reads the latest target.
    const transition = document.startViewTransition(() => flushSync(() => setShown(latest.current)))
    running.current = transition
    const clear = () => {
      if (running.current === transition) running.current = null
    }
    transition.finished.then(clear, clear)
    // Skipping rejects `ready`; that is the intended interrupt, not an error.
    transition.ready.catch(() => undefined)
  }, [location]) // Only a location change starts a fade; the other inputs are read as they stand.

  return shown
}
