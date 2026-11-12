import { describe, expect, it } from 'vitest'
import type { NhlGameContext, NhlGoalieSide } from '~/types/nhlContext'
import { filterStartingGoalie, goalieSides, parseGoalieFilter, type NhlGoalieSides } from '~/utils/nhlGoalieFilter'
import { ALL, filterBoardMarkets } from '~/utils/propFilters'

const NOW = new Date('2026-11-11T22:00:00Z')
const START = '2026-11-12T00:00:00Z'
const FRESH = '2026-11-11T21:00:00Z'

const TBL_CHI = { gameId: 1, awayTeam: 'TBL', homeTeam: 'CHI' }

function side(team: string, status: NhlGoalieSide['status'], playerId: number | null = null): NhlGoalieSide {
  return { team, espnAthleteId: null, playerId, playerName: null, status, rawStatus: null, linkReason: null }
}

function sides(away: NhlGoalieSide['status'], home: NhlGoalieSide['status'], awayId: number | null = 30, homeId: number | null = 31): Map<number, NhlGoalieSides> {
  return new Map([[1, { away: side('TBL', away, awayId), home: side('CHI', home, homeId) }]])
}

function context(fetchedAt: string | null, freshness: 'fresh' | 'stale' | 'unavailable' = 'fresh'): NhlGameContext {
  const source = { source: 'ESPN' as const, fetchedAt, sourceTimestamp: fetchedAt, freshness }
  return { injuries: { ...source, away: [], home: [] }, goalies: { ...source, away: side('TBL', 'confirmed', 30), home: side('CHI', 'expected', 31) } }
}

function row(playerId: number, team: string | null, market = 'shots_on_goal', game = TBL_CHI) {
  return { key: `${game.gameId}:${playerId}:${market}`, game, row: { playerId, playerName: `Player ${playerId}`, team, market } }
}

const ids = <M extends { rows: Array<{ row: { playerId: number } }> }>(markets: M[]) => markets.map(market => market.rows.map(entry => entry.row.playerId))

describe('parseGoalieFilter', () => {
  it('reads confirmed and known, and anything else as any', () => {
    expect(parseGoalieFilter(new URLSearchParams('goalie=confirmed'))).toBe('confirmed')
    expect(parseGoalieFilter(new URLSearchParams('goalie=known'))).toBe('known')
    expect(parseGoalieFilter(new URLSearchParams('goalie=expected'))).toBe('any')
    expect(parseGoalieFilter(new URLSearchParams())).toBe('any')
  })
})

describe('goalieSides', () => {
  it('keeps a game only from a fresh report', () => {
    const games = [
      { gameId: 1, startUtc: START, context: context(FRESH) },
      { gameId: 2, startUtc: START, context: context(FRESH, 'stale') },
      { gameId: 3, startUtc: START, context: context(null, 'unavailable') },
      { gameId: 4, startUtc: START, context: context('2026-11-11T10:00:00Z') },
    ]
    const map = goalieSides(games, NOW)
    expect([...map.keys()]).toEqual([1])
    expect(map.get(1)?.away.status).toBe('confirmed')
  })
})

describe('filterStartingGoalie', () => {
  const skaters = [{ market: 'shots_on_goal', rows: [row(1, 'TBL'), row(2, 'CHI')] }]

  it('judges a skater by the goalie he faces, not his own', () => {
    expect(ids(filterStartingGoalie(skaters, 'confirmed', sides('confirmed', 'expected')))).toEqual([[2]])
    expect(ids(filterStartingGoalie(skaters, 'known', sides('confirmed', 'expected')))).toEqual([[1, 2]])
  })

  it.each([
    ['confirmed', 'confirmed', [2]],
    ['expected', 'confirmed', []],
    ['expected', 'known', [2]],
    ['unknown', 'known', []],
    ['not_reported', 'known', []],
    ['unavailable', 'known', []],
  ] as const)('a %s opposing starter under %s', (status, filter, expected) => {
    expect(ids(filterStartingGoalie(skaters, filter, sides(status, 'unknown')))).toEqual([expected])
  })

  it('keeps a goalie row only for his own team\'s listed starter', () => {
    const goalies = [{ market: 'goalie_saves', rows: [row(30, 'TBL', 'goalie_saves'), row(99, 'TBL', 'goalie_saves'), row(31, 'CHI', 'goalie_saves')] }]
    expect(ids(filterStartingGoalie(goalies, 'confirmed', sides('confirmed', 'expected')))).toEqual([[30]])
    expect(ids(filterStartingGoalie(goalies, 'known', sides('confirmed', 'expected')))).toEqual([[30, 31]])
  })

  it('drops a goalie row when the listed starter is not linked to a player', () => {
    const goalies = [{ market: 'goals_allowed', rows: [row(30, 'TBL', 'goals_allowed')] }]
    expect(ids(filterStartingGoalie(goalies, 'known', sides('confirmed', 'confirmed', null)))).toEqual([[]])
  })

  it('never passes a game missing from the slate or a team it cannot place', () => {
    const other = { gameId: 2, awayTeam: 'NYR', homeTeam: 'BOS' }
    const markets = [{ market: 'points', rows: [row(5, 'NYR', 'points', other), row(6, null, 'points'), row(7, 'TBL', 'points')] }]
    expect(ids(filterStartingGoalie(markets, 'known', sides('confirmed', 'confirmed')))).toEqual([[7]])
  })

  it('places a PrizePicks code that differs from the game code', () => {
    const markets = [{ market: 'points', rows: [row(8, 'TB', 'points')] }]
    expect(ids(filterStartingGoalie(markets, 'confirmed', sides('unknown', 'confirmed')))).toEqual([[8]])
  })

  it('returns the markets unchanged for any and keeps emptied markets', () => {
    expect(filterStartingGoalie(skaters, 'any', new Map())).toBe(skaters)
    const filtered = filterStartingGoalie([...skaters, { market: 'hits', rows: [] }], 'confirmed', new Map())
    expect(filtered.map(market => market.market)).toEqual(['shots_on_goal', 'hits'])
    expect(ids(filtered)).toEqual([[], []])
  })

  it('composes after the board filters', () => {
    const named = filterBoardMarkets(skaters, { players: ['Player 1'], team: ALL, games: [] })
    expect(ids(filterStartingGoalie(named, 'known', sides('expected', 'confirmed')))).toEqual([[1]])
  })
})
