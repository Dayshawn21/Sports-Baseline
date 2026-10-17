import { describe, expect, it } from 'vitest'
import { DEV_API_BASE, resolveApiBaseUrl } from '~/utils/apiBase'

describe('resolveApiBaseUrl', () => {
  it('falls back to the dev proxy path when unset or blank', () => {
    expect(resolveApiBaseUrl(undefined)).toBe(DEV_API_BASE)
    expect(resolveApiBaseUrl('')).toBe(DEV_API_BASE)
    expect(resolveApiBaseUrl('   ')).toBe(DEV_API_BASE)
  })

  it('returns a deployed origin trimmed and without a trailing slash', () => {
    expect(resolveApiBaseUrl('https://sportapp-api.onrender.com')).toBe('https://sportapp-api.onrender.com')
    expect(resolveApiBaseUrl(' https://sportapp-api.onrender.com/ ')).toBe('https://sportapp-api.onrender.com')
    expect(resolveApiBaseUrl('http://127.0.0.1:8000//')).toBe('http://127.0.0.1:8000')
  })

  it('rejects a value that is not an http(s) origin', () => {
    expect(() => resolveApiBaseUrl('sportapp-api.onrender.com')).toThrow(/VITE_API_BASE_URL/)
    expect(() => resolveApiBaseUrl('ftp://example.com')).toThrow(/VITE_API_BASE_URL/)
    expect(() => resolveApiBaseUrl('https://')).toThrow(/VITE_API_BASE_URL/)
  })
})
