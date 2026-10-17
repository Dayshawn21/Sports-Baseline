import { describe, expect, it } from 'vitest'
import { nflBookOddsEvidence } from './nflBookOdds'

const NOW = Date.parse('2026-09-20T14:00:00Z')
const priced = {
  projection: 0.22,
  bookProbability: 0.5402,
  bookProbabilityDevigged: null,
  bookCount: 6,
  bookIncludesMargin: true,
  bookFetchedAt: '2026-09-18T21:00:00Z',
}

describe('nflBookOddsEvidence', () => {
  it('shows consensus, book count, age, and the model gap in points', () => {
    expect(nflBookOddsEvidence(priced, NOW)).toEqual({
      summary: '54.0% · 6 books · 41h ago',
      comparison: 'Model -32.0 pts vs books · includes book margin',
    })
  })

  it('omits the margin note for de-vigged prices and signs a positive gap', () => {
    const result = nflBookOddsEvidence({ ...priced, projection: 0.6, bookIncludesMargin: false, bookCount: 1, bookFetchedAt: '2026-09-20T13:30:00Z' }, NOW)
    expect(result).toEqual({ summary: '54.0% · 1 book · 30m ago', comparison: 'Model +6.0 pts vs books' })
  })

  it('switches to days for old prices and handles a missing baseline', () => {
    const result = nflBookOddsEvidence({ ...priced, projection: null, bookFetchedAt: '2026-09-15T14:00:00Z' }, NOW)
    expect(result).toEqual({ summary: '54.0% · 6 books · 5d ago', comparison: 'No model baseline · includes book margin' })
  })

  it('leads with the de-vigged price and compares the model against it', () => {
    const result = nflBookOddsEvidence({ ...priced, bookProbabilityDevigged: 0.4712 }, NOW)
    expect(result).toEqual({
      summary: '47.1% de-vigged · 6 books · 41h ago',
      comparison: 'Model -25.1 pts vs books · 54.0% raw',
    })
  })

  it('keeps the raw price visible rather than replacing it', () => {
    const result = nflBookOddsEvidence({ ...priced, projection: null, bookProbabilityDevigged: 0.4712 }, NOW)
    expect(result?.comparison).toBe('No model baseline · 54.0% raw')
  })

  it('is null when no book priced the line', () => {
    expect(nflBookOddsEvidence({ ...priced, bookProbability: null, bookCount: null, bookIncludesMargin: null, bookFetchedAt: null }, NOW)).toBeNull()
  })
})
