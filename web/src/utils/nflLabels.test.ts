import { describe, expect, it } from 'vitest'
import { formatHistoryValue, formatKickoffTime, formatProjection, formatTime, matchupAllowedLabel } from './nflLabels'

describe('formatTime', () => {
  it('formats kickoff times in Central Time', () => {
    expect(formatTime('2026-09-17T20:15:00Z')).toBe('9/17/2026, 3:15:00 PM CDT')
  })

  it('handles a missing kickoff time', () => {
    expect(formatTime(null)).toBe('Start time unavailable')
  })
})

describe('formatKickoffTime', () => {
  it('shows a compact Central kickoff time for board rows', () => {
    expect(formatKickoffTime('2026-09-20T17:00:00Z')).toBe('12:00 PM CDT')
  })

  it('returns no label when the kickoff is unavailable', () => {
    expect(formatKickoffTime(null)).toBe('')
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
