import { describe, expect, it } from 'vitest'
import type { NbaInjury, NbaInjuryReport, NbaLineOnlyLine, NbaPropLine } from '~/types/nba'
import { nbaInjuryFreshness, nbaInjuryTime, UNAVAILABLE_NBA_INJURIES } from '~/utils/nbaInjuries'
import { nbaPropGroups } from '~/utils/nbaProps'
import { nbaLineOnlyGroups } from '~/utils/nbaLineOnly'
import { nbaPropBoard } from '~/utils/nbaPropBoard'

const NOW = new Date('2026-10-21T18:00:00Z')
const TIP = '2026-10-21T20:00:00Z'
const INJURY: NbaInjury = {
  espnAthleteId: '123', playerId: 1, playerName: 'Fixture player', team: 'NY', athleteTeam: 'NY',
  status: 'Out', detail: 'Ankle', sourceUpdatedAt: '2026-10-21T16:00:00Z', returnDate: null,
  fetchedAt: '2026-10-21T17:00:00Z',
}
const REPORT: NbaInjuryReport = { source: 'ESPN', fetchedAt: INJURY.fetchedAt, freshness: 'fresh', injuries: [INJURY] }

function line(overrides: Partial<NbaPropLine> = {}): NbaPropLine {
  return {
    playerId: 1, playerName: 'Fixture player', position: 'G', team: 'NY', market: 'assists', oddsType: 'standard',
    line: 4.5, fetchedAt: '2026-10-21T16:00:00Z', recent: [], injury: INJURY,
    projection: 5, gap: 0.5, pOver: 0.55, pUnder: 0.45, gamesInSample: 20, priorMinutes: 32,
    overProbabilityVersion: 'nba-pover-v1', flags: [], ...overrides,
  }
}

describe('injury freshness', () => {
  it.each([
    ['2026-10-21T17:00:00Z', TIP, NOW, 'fresh'],
    ['2026-10-21T12:00:00Z', TIP, NOW, 'fresh'],
    ['2026-10-21T11:59:59.999Z', TIP, NOW, 'stale'],
    ['2026-10-21T18:01:00Z', TIP, NOW, 'unavailable'],
    [TIP, TIP, new Date(TIP), 'unavailable'],
    ['2026-10-21T17:00:00Z', null, NOW, 'unavailable'],
    ['invalid', TIP, NOW, 'unavailable'],
    [null, TIP, NOW, 'unavailable'],
    ['2026-10-21T17:00:00Z', '2026-10-21T18:00:00Z', new Date('2026-11-01T18:00:00Z'), 'fresh'],
  ])('handles fetch %s and tip %s', (fetchedAt, tip, now, expected) => {
    expect(nbaInjuryFreshness({ ...REPORT, fetchedAt }, tip, now)).toBe(expected)
  })

  it('respects unavailable and stale reports, and rejects invalid clocks/tips', () => {
    expect(nbaInjuryFreshness(undefined, TIP, NOW)).toBe('unavailable')
    expect(nbaInjuryFreshness(UNAVAILABLE_NBA_INJURIES, TIP, NOW)).toBe('unavailable')
    expect(nbaInjuryFreshness({ ...REPORT, freshness: 'stale' }, TIP, NOW)).toBe('stale')
    expect(nbaInjuryFreshness(REPORT, 'invalid', NOW)).toBe('unavailable')
    expect(nbaInjuryFreshness(REPORT, TIP, new Date(NaN))).toBe('unavailable')
  })

  it('does not turn null player context into a healthy status', () => {
    const [group] = nbaPropGroups([line({ injury: null })])
    expect(group.cards[0].injury).toBeNull()
    expect(nbaInjuryFreshness({ ...REPORT, injuries: [] }, TIP, NOW)).toBe('fresh')
  })
})

describe('injury grouping', () => {
  it('preserves injury and every alternate rung in both grouping helpers', () => {
    const lines = [line({ line: 6.5, oddsType: 'demon' }), line()]
    const modelled = nbaPropGroups(lines)[0].cards[0]
    const plain: NbaLineOnlyLine[] = lines.map(row => ({ ...row, market: 'double_double' }))
    const other = nbaLineOnlyGroups(plain)[0].rows[0]
    expect(modelled.injury).toEqual(INJURY)
    expect(other.injury).toEqual(INJURY)
    expect(modelled.rungs.map(row => row.line)).toEqual([4.5, 6.5])
    expect(other.rungs.map(row => row.line)).toEqual([4.5, 6.5])
    expect(modelled.projectionRow).toEqual({ projection: '5.0', gap: '+0.5', pOver: '55%', pUnder: '45%' })
  })

  it('keeps injury/report context tied to each game without changing order', () => {
    const games = [
      { gameId: 7, awayTeam: 'NY', homeTeam: 'BOS', startUtc: TIP, status: 'scheduled',
        lines: [line()], lineOnlyLines: [], injuryReport: REPORT, teamStats: null },
      { gameId: 8, awayTeam: 'NY', homeTeam: 'BOS', startUtc: TIP, status: 'scheduled',
        lines: [line({ injury: null })], lineOnlyLines: [], injuryReport: UNAVAILABLE_NBA_INJURIES, teamStats: null },
    ]
    const rows = nbaPropBoard(games).find(group => group.market === 'assists')!.rows
    expect(rows.map(row => row.game.gameId)).toEqual([7, 8])
    expect(rows[0].row.injury).toEqual(INJURY)
    expect(rows[1].row.injury).toBeNull()
    expect(rows[1].game.injuryReport.freshness).toBe('unavailable')
    games[0].lines[0] = line({ injury: null })
    expect(nbaPropBoard(games).find(group => group.market === 'assists')!.rows[0].row.injury).toBeNull()
  })
})

describe('injury source times', () => {
  it('uses a dated CT timestamp through summer and winter and keeps missing values missing', () => {
    expect(nbaInjuryTime('2026-10-21T17:00:00Z')).toBe('Oct 21, 2026, 12:00 PM CT')
    expect(nbaInjuryTime('2026-12-21T17:00:00Z')).toBe('Dec 21, 2026, 11:00 AM CT')
    expect(nbaInjuryTime(null)).toBe('Time unavailable')
    expect(nbaInjuryTime('invalid')).toBe('Time unavailable')
  })
})
