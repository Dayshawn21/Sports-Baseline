import { useSyncExternalStore } from 'react'

// Matches the slate stylesheets' phone breakpoint.
const QUERY = '(max-width: 767px)'

function subscribe(onChange: () => void): () => void {
  const media = window.matchMedia(QUERY)
  media.addEventListener('change', onChange)
  return () => media.removeEventListener('change', onChange)
}

/** True at phone width, for content that moves in the DOM (not only in CSS) so focus order follows what is seen. */
export function usePhoneLayout(): boolean {
  return useSyncExternalStore(subscribe, () => window.matchMedia(QUERY).matches, () => false)
}
