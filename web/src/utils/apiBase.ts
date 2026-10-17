// Unset in dev, where the Vite proxy serves the API under /api; set at build time
// for a deploy whose API lives on its own origin.
export const DEV_API_BASE = '/api'

export function resolveApiBaseUrl(value: string | undefined): string {
  const trimmed = value?.trim() ?? ''
  if (!trimmed) return DEV_API_BASE
  if (!/^https?:\/\/[^/]/.test(trimmed)) {
    throw new Error(`VITE_API_BASE_URL must be an http(s) origin, got "${trimmed}"`)
  }
  return trimmed.replace(/\/+$/, '')
}
