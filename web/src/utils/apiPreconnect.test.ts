import { describe, expect, it } from 'vitest'
import { apiPreconnectTag } from '~/utils/apiPreconnect'

describe('apiPreconnectTag', () => {
  it('adds nothing in dev, where the API is proxied on the page origin', () => {
    expect(apiPreconnectTag(undefined)).toBeNull()
    expect(apiPreconnectTag('')).toBeNull()
    expect(apiPreconnectTag('  ')).toBeNull()
  })

  it('preconnects to the origin only, without a trailing slash or path', () => {
    expect(apiPreconnectTag('https://sportapp-api-ftsf.onrender.com')).toEqual({ href: 'https://sportapp-api-ftsf.onrender.com' })
    expect(apiPreconnectTag(' https://sportapp-api-ftsf.onrender.com/ ')).toEqual({ href: 'https://sportapp-api-ftsf.onrender.com' })
    expect(apiPreconnectTag('http://127.0.0.1:8000/v1/')).toEqual({ href: 'http://127.0.0.1:8000' })
  })

  it('rejects a value the API client would reject too', () => {
    expect(() => apiPreconnectTag('sportapp-api-ftsf.onrender.com')).toThrow(/VITE_API_BASE_URL/)
  })
})
