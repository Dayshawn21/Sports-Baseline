import { describe, expect, it } from 'vitest'
import type { MatchResearch, MatchResearchStats } from '~/types/tennis'
import { researchDate, researchPair, researchTimestamp, workloadSets } from '~/utils/tennisResearch'

const stats: MatchResearchStats = {
  surface: 'Hard', matchesCount: 5, computedAt: null, winRate: .6, holdPct: .8,
  returnPointsWon: .35, breakConversionPct: .4, firstInPct: .6,
  firstServeWon: .7, secondServeWon: .5, firstReturnWon: .3, secondReturnWon: .5,
  thinSample: true, statPeriod: 'last_52w', source: 'TennisAbstract', snapshotBasis: 'Current',
}
const workload = {
  windowStart: '2026-10-15', windowEndExclusive: '2026-10-22', previousMatchDate: null,
  calendarDaysSinceMatch: null, matchesPlayed: 0, completedSets: 0,
  matchesWithCompleteScores: 0, minutesPlayed: null, dateBasis: 'UTC', historyLookbackDays: 365, source: 'Stored matches',
}
const player = (playerId: number, surfaceStats: MatchResearchStats | null) => ({
  playerId, surfaceStats, overallStats: { ...stats, surface: null, matchesCount: 30, thinSample: false },
  eloAsOfDate: null, workload,
})
const research: MatchResearch = {
  players: [player(2, { ...stats, matchesCount: 10 }), player(1, stats)],
  odds: [], oddsCutoff: '', eloSource: '',
}
const match = { p1: { playerId: 1 }, p2: { playerId: 2 }, surface: 'Hard', research }

describe('match research comparison', () => {
  it('maps the correct player by ID and preserves thin samples for display', () => {
    const [left, right] = researchPair(match, false)
    expect(left).toMatchObject({ surface: 'Hard', matchesCount: 5, thinSample: true })
    expect(right?.matchesCount).toBe(10)
  })
  it('requires an explicit overall choice rather than filling missing surface stats', () => {
    const missing = { ...match, research: { ...research, players: [player(1, null)] } }
    expect(researchPair(missing, false)).toEqual([null, null])
    expect(researchPair(missing, true)[0]).toMatchObject({ surface: null, matchesCount: 30 })
  })
  it('does not show a different surface or window as this match surface', () => {
    expect(researchPair({ ...match, surface: 'Clay' }, false)).toEqual([null, null])
    expect(researchPair({ ...match, surface: null }, false)).toEqual([null, null])
    const wrongWindow = { ...match, research: { ...research, players: [player(1, { ...stats, statPeriod: 'last_10' })] } }
    expect(researchPair(wrongWindow, false)[0]).toBeNull()
  })
  it('does not label a surface split as all-surface data', () => {
    const wrongOverall = { ...match, research: { ...research, players: [{ ...player(1, stats), overallStats: stats }] } }
    expect(researchPair(wrongOverall, true)[0]).toBeNull()
  })
  it('keeps missing research and individual missing values explicit', () => {
    expect(researchPair({ ...match, research: null }, false)).toEqual([null, null])
    const missingRate = { ...match, research: { ...research, players: [player(1, { ...stats, secondReturnWon: null })] } }
    expect(researchPair(missingRate, false)[0]?.secondReturnWon).toBeNull()
  })
})

describe('research dates and workload coverage', () => {
  it('preserves date-only records without moving them into the previous CT day', () => {
    expect(researchDate('2026-10-22')).toBe('Oct 22, 2026')
    expect(researchDate('2024-02-29')).toBe('Feb 29, 2024')
  })
  it.each([null, undefined, '', 'bad', '2026-02-30', '2026-10-22T03:15:00Z'])('labels invalid date %s unavailable', value => {
    expect(researchDate(value)).toBe('Unavailable')
  })
  it('formats aware timestamps across a CT calendar-day boundary', () => {
    expect(researchTimestamp('2026-10-22T03:15:00Z')).toBe('Oct 21, 2026, 10:15 PM CT')
    expect(researchTimestamp('2026-01-10T03:15:00Z')).toBe('Jan 9, 2026, 9:15 PM CT')
    expect(researchTimestamp('2026-10-22T03:15:00+02:00')).toBe('Oct 21, 2026, 8:15 PM CT')
  })
  it('honors Central Time daylight saving transitions', () => {
    expect(researchTimestamp('2026-03-08T07:30:00Z')).toBe('Mar 8, 2026, 1:30 AM CT')
    expect(researchTimestamp('2026-03-08T08:30:00Z')).toBe('Mar 8, 2026, 3:30 AM CT')
  })
  it.each([null, undefined, '', 'bad', '2026-10-22', '2026-10-22Z', '2026-10-22T03:15:00', '2026-02-30T03:15:00Z'])('does not guess a timezone or missing timestamp %s', value => {
    expect(researchTimestamp(value)).toBe('Unavailable')
  })
  it('shows incomplete set totals as lower bounds and distinguishes unknown from zero', () => {
    expect(workloadSets({ ...workload, completedSets: 5, matchesPlayed: 3, matchesWithCompleteScores: 2 })).toBe('At least 5')
    expect(workloadSets({ ...workload, completedSets: 5, matchesPlayed: 3, matchesWithCompleteScores: 3 })).toBe('5')
    expect(workloadSets({ ...workload, matchesPlayed: 3 })).toBe('Unavailable')
    expect(workloadSets(workload)).toBe('0')
    expect(workloadSets(null)).toBe('Unavailable')
  })
})
