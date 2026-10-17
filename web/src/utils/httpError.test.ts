import { AxiosError, type AxiosResponse } from 'axios'
import { describe, expect, it } from 'vitest'
import {
  httpStatus,
  isNotFound,
  retryAfterSeconds,
  retryUnlessAuthOrLimited,
  retryUnlessNotFound,
} from '~/utils/httpError'

function httpError(status: number, headers: Record<string, string> = {}): AxiosError {
  return new AxiosError('failed', 'ERR_BAD_REQUEST', undefined, undefined, { status, headers } as AxiosResponse)
}

describe('isNotFound', () => {
  it('is true only for an HTTP 404', () => {
    expect(isNotFound(httpError(404))).toBe(true)
    expect(isNotFound(httpError(500))).toBe(false)
    expect(isNotFound(new AxiosError('offline'))).toBe(false)
    expect(isNotFound(new Error('boom'))).toBe(false)
  })
})

describe('retryUnlessNotFound', () => {
  it('never retries a 404', () => {
    expect(retryUnlessNotFound(0, httpError(404))).toBe(false)
  })

  it('retries other failures twice, like the app default', () => {
    expect(retryUnlessNotFound(0, httpError(500))).toBe(true)
    expect(retryUnlessNotFound(1, httpError(500))).toBe(true)
    expect(retryUnlessNotFound(2, httpError(500))).toBe(false)
  })
})

describe('httpStatus', () => {
  it('reads the status of an HTTP error only', () => {
    expect(httpStatus(httpError(401))).toBe(401)
    expect(httpStatus(new AxiosError('offline'))).toBeUndefined()
    expect(httpStatus(new Error('boom'))).toBeUndefined()
  })
})

describe('retryAfterSeconds', () => {
  it('reads whole seconds from Retry-After', () => {
    expect(retryAfterSeconds(httpError(429, { 'retry-after': '42' }))).toBe(42)
    expect(retryAfterSeconds(httpError(429, { 'retry-after': '0.4' }))).toBe(1)
  })

  it('is null when the header is missing or not a number', () => {
    expect(retryAfterSeconds(httpError(429))).toBeNull()
    expect(retryAfterSeconds(httpError(429, { 'retry-after': '' }))).toBeNull()
    expect(retryAfterSeconds(httpError(429, { 'retry-after': 'soon' }))).toBeNull()
    expect(retryAfterSeconds(new Error('boom'))).toBeNull()
  })
})

describe('retryUnlessAuthOrLimited', () => {
  it('never retries a rejected key or a rate limit', () => {
    expect(retryUnlessAuthOrLimited(0, httpError(401))).toBe(false)
    expect(retryUnlessAuthOrLimited(0, httpError(429))).toBe(false)
  })

  it('retries other failures twice', () => {
    expect(retryUnlessAuthOrLimited(1, httpError(500))).toBe(true)
    expect(retryUnlessAuthOrLimited(2, httpError(500))).toBe(false)
    expect(retryUnlessAuthOrLimited(0, new AxiosError('offline'))).toBe(true)
  })
})
