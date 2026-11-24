import { describe, expect, it } from 'vitest'
import { askErrorMessage, askRetryable } from '~/utils/askError'

describe('askErrorMessage', () => {
  it("shows the API's own 429 and 503 copy when it sent one", () => {
    expect(askErrorMessage(429, 'Daily limit reached.')).toBe('Daily limit reached.')
    expect(askErrorMessage(503, 'Spending cap reached.')).toBe('Spending cap reached.')
  })

  it('falls back to fixed copy for a 429 or 503 with no detail', () => {
    expect(askErrorMessage(429)).toBe("You're asking faster than Lineform allows. Try again in a minute.")
    expect(askErrorMessage(503)).toBe('Ask Lineform is off right now.')
  })

  it('ignores a detail on other statuses', () => {
    expect(askErrorMessage(404, 'Not Found')).toBe('Ask Lineform is off right now.')
    expect(askErrorMessage(422, 'body.question: too long')).toBe('Ask a question of up to 500 characters.')
    expect(askErrorMessage(500, 'Traceback')).toBe('Something went wrong answering that. Try again.')
  })

  it('names a network failure', () => {
    expect(askErrorMessage(null)).toBe("Couldn't reach Lineform. Check your connection and try again.")
  })
})

describe('askRetryable', () => {
  it('never retries Ask being off or a rejected question', () => {
    expect(askRetryable(404)).toBe(false)
    expect(askRetryable(422)).toBe(false)
  })

  it('retries a 429 only when the wait is short or unknown', () => {
    expect(askRetryable(429)).toBe(true)
    expect(askRetryable(429, null, 60)).toBe(true)
    expect(askRetryable(429, null, 61)).toBe(false)
    expect(askRetryable(429, 'Daily limit reached.', 3600)).toBe(false)
  })

  it('retries a 503 only when the API did not explain it', () => {
    expect(askRetryable(503)).toBe(true)
    expect(askRetryable(503, 'Spending cap reached.')).toBe(false)
  })

  it('retries network failures and server errors', () => {
    expect(askRetryable(null)).toBe(true)
    expect(askRetryable(500)).toBe(true)
    expect(askRetryable(502)).toBe(true)
  })
})
