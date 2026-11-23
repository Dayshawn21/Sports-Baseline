import { DEV_API_BASE, resolveApiBaseUrl } from './apiBase'

/**
 * The `<link rel="preconnect">` for a build whose API lives on its own origin, or null in dev, where Vite
 * proxies `/api` on the page's origin. `crossorigin` matches the API's CORS requests (no credentials), so the
 * browser reuses this socket for them. Without it the first API call paid DNS, TCP and TLS after the JS loaded:
 * Lighthouse estimated 345 ms of LCP on the home page (2026-11-23).
 */
export function apiPreconnectTag(value: string | undefined): { href: string } | null {
  const base = resolveApiBaseUrl(value)
  if (base === DEV_API_BASE) return null
  return { href: new URL(base).origin }
}
