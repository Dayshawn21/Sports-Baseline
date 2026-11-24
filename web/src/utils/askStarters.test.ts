import { describe, expect, it } from 'vitest'
import { askErrorMessage, askRetryable } from '~/utils/askError'
import { askStarters } from '~/utils/askStarters'

describe('askStarters', () => {
  it.each(['nba', 'nfl', 'tennis'] as const)('offers three %s questions', sport => {
    const starters = askStarters(sport)
    expect(starters).toHaveLength(3)
    expect(starters).not.toEqual(askStarters(null))
  })

  it('uses the general set off a sport page and on NHL, which Ask does not cover', () => {
    expect(askStarters(null)).toHaveLength(3)
    expect(askStarters('nhl')).toEqual(askStarters(null))
  })
})

describe('askErrorMessage', () => {
  it.each([
    [429, /faster than Lineform allows/],
    [404, /off right now/],
    [503, /off right now/],
    [422, /500 characters/],
    [null, /Couldn't reach Lineform/],
    [500, /Something went wrong/],
  ] as const)('explains %s', (status, copy) => {
    expect(askErrorMessage(status)).toMatch(copy)
  })
})

describe('askRetryable', () => {
  it.each([
    ['the daily limit', 429, "You've used today's 20 questions. Try again tomorrow.", 86_000],
    ['the spending cap', 503, "Ask Lineform has reached today's limit. It resets at midnight UTC.", null],
    ['no key', 503, 'Ask Lineform is not configured', null],
    ['Ask off', 404, 'Not Found', null],
    ['a rejected question', 422, null, null],
  ] as const)('offers no retry for %s', (_case, status, detail, retryAfter) => {
    expect(askRetryable(status, detail, retryAfter)).toBe(false)
  })

  it.each([
    ['the per-minute limit', 429, 'Too many requests. Try again shortly.', 42],
    ['a 429 with no Retry-After', 429, null, null],
    ['a proxy 503 with no API detail', 503, null, null],
    ['a server error', 500, null, null],
    ['a network failure', null, null, null],
  ] as const)('offers a retry for %s', (_case, status, detail, retryAfter) => {
    expect(askRetryable(status, detail, retryAfter)).toBe(true)
  })
})
