import { describe, expect, it } from 'vitest'
import { formatHistoryValue, formatKickoffTime, formatProjection, formatTime, matchupAllowedLabel } from './nflLabels'

describe('formatTime', () => {
  it.each([
    ['2026-01-15T18:00:00Z', '1/15/2026, 12:00:00 PM CT'],
    ['2026-07-15T18:00:00Z', '7/15/2026, 1:00:00 PM CT'],
    ['2026-07-01T04:30:00Z', '6/30/2026, 11:30:00 PM CT'],
    ['2026-07-01T05:00:00Z', '7/1/2026, 12:00:00 AM CT'],
  ])('formats %s with the Central date and offset', (value, expected) => {
    expect(formatTime(value)).toBe(expected)
  })

  it.each([null, '', 'not a date', '2026-99-99T00:00:00Z'])('handles an unavailable kickoff: %s', value => {
    expect(formatTime(value)).toBe('Start time unavailable')
  })
})

describe('formatKickoffTime', () => {
  it.each([
    ['2026-01-15T18:00:00Z', '12:00 PM CT'],
    ['2026-07-15T18:00:00Z', '1:00 PM CT'],
    ['2026-07-01T04:30:00Z', '11:30 PM CT'],
    ['2026-07-01T05:00:00Z', '12:00 AM CT'],
  ])('shows a compact Central kickoff for %s', (value, expected) => {
    expect(formatKickoffTime(value)).toBe(expected)
  })

  it.each([null, '', 'not a date', '2026-99-99T00:00:00Z'])('returns no label for an unavailable kickoff: %s', value => {
    expect(formatKickoffTime(value)).toBe('')
  })
})

describe('formatHistoryValue', () => {
  it('shows scored or not for a past anytime TD game', () => {
    expect(formatHistoryValue('anytime_touchdown', 1)).toBe('TD')
    expect(formatHistoryValue('anytime_touchdown', 0)).toBe('No TD')
  })

  it('shows the stat for every other market', () => {
    expect(formatHistoryValue('receiving_yards', 61)).toBe('61.0')
  })
})

describe('formatProjection', () => {
  it('shows an anytime TD average as the share of games', () => {
    expect(formatProjection('anytime_touchdown', 0.4)).toBe('40.0%')
  })
})

describe('matchupAllowedLabel', () => {
  it('labels a team-game market as the position total per game', () => {
    expect(matchupAllowedLabel('passing_completions', 'QB', 20.59, 17)).toBe('20.6 to QBs per game · 17 games')
    expect(matchupAllowedLabel('passing_completions', null, 20.59, 17)).toBe('20.6 to the position per game · 17 games')
  })

  it('keeps the per-player wording for every other market', () => {
    expect(matchupAllowedLabel('receiving_yards', 'WR', 42.04, 51)).toBe('42.0 allowed · 51 games')
    expect(matchupAllowedLabel('anytime_touchdown', 'RB', 0.321, null)).toBe('32.1% allowed · 0 games')
  })
})
