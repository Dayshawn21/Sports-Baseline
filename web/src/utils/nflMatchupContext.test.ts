import { describe, expect, it } from 'vitest'
import type { NflContextMetric, NflContextPlayer } from '~/types/nfl'
import { POSITION_ALLOWED_ROWS, contextCoverage, contextDates, contextRank, contextUnavailable, contextValue, orderedContextPlayers } from './nflMatchupContext'

const METRIC: NflContextMetric = {
  value: 0.25, observedGames: 2, eligibleGames: 3,
  windowStart: '2026-09-13', windowEnd: '2026-10-18', reason: null,
}

describe('context values and coverage', () => {
  it('formats fractions as percentages and counts to one decimal', () => {
    expect(contextValue(METRIC, true)).toBe('25.0%')
    expect(contextValue({ ...METRIC, value: 12 })).toBe('12.0')
    expect(contextValue({ ...METRIC, value: -2 })).toBe('-2.0')
  })
  it('separates observed zero from missing', () => {
    expect(contextValue({ ...METRIC, value: 0 }, true)).toBe('0.0%')
    expect(contextValue({ ...METRIC, value: null })).toBe('-')
    expect(contextValue({ ...METRIC, value: null }, true)).toBe('-')
  })
  it('shows actual coverage and no percentage when no games are eligible', () => {
    expect(contextCoverage(METRIC)).toBe('2 / 3 games (67%)')
    expect(contextCoverage({ ...METRIC, observedGames: 0 })).toBe('0 / 3 games (0%)')
    expect(contextCoverage({ ...METRIC, observedGames: 0, eligibleGames: 0 })).toBe('0 eligible games')
  })
  it('uses the returned ranked-team count and preserves competition ties', () => {
    expect(contextRank({ ...METRIC, rank: 2, rankedTeams: 28 })).toBe('Rank 2 / 28')
    expect(contextRank({ ...METRIC, value: null, rank: null, rankedTeams: 28 })).toBe('Unranked')
  })
})

describe('observed game dates', () => {
  it('uses UTC calendar dates without shifting to the browser timezone', () => {
    expect(contextDates(METRIC)).toBe('Sep 13 - Oct 18')
    expect(contextDates({ ...METRIC, windowEnd: METRIC.windowStart })).toBe('Sep 13')
  })
  it.each([null, '', 'bad-date', '2026-02-30', '2026-13-01'])('omits unavailable or invalid boundaries: %s', value => {
    expect(contextDates({ ...METRIC, windowStart: value })).toBeNull()
    expect(contextDates({ ...METRIC, windowEnd: value })).toBeNull()
  })
})

describe('unavailable explanations', () => {
  it.each([
    ['no_history', 'No pre-week games'], ['missing_data', 'Metric not loaded'],
    ['zero_denominator', 'Team total is zero'], ['unknown_kickoff', 'Kickoff time unavailable'],
    [null, 'Unavailable'],
  ] as const)('explains %s', (reason, message) => {
    expect(contextUnavailable({ ...METRIC, value: null, reason })).toBe(message)
  })
  it('does not label an observed zero unavailable', () => {
    expect(contextUnavailable({ ...METRIC, value: 0 })).toBeNull()
  })
})

it('orders the complete roster by team, name and ID without mutating or selecting by share', () => {
  const window = { targets: METRIC, carries: METRIC, targetShare: METRIC, carryShare: METRIC, avgGameSnapShare: METRIC, teams: ['A'] }
  const player = (playerId: number, team: string, name: string): NflContextPlayer => ({
    playerId, team, name, position: 'WR', seasonUsage: window, recentUsage: window,
  })
  const players = [player(3, 'B', 'Ada'), player(8, 'A', 'Zed'), player(2, 'A', 'Ada'), player(1, 'A', 'Ada')]
  expect(orderedContextPlayers(players).map(row => row.playerId)).toEqual([1, 2, 8, 3])
  expect(players.map(row => row.playerId)).toEqual([3, 8, 2, 1])
})

it('includes only the eight specified position measures', () => {
  expect(POSITION_ALLOWED_ROWS.map(row => row.key)).toEqual([
    'rbCarries', 'rbRushYards', 'rbReceptions', 'rbRecYards', 'wrReceptions', 'wrRecYards', 'teReceptions', 'teRecYards',
  ])
})
