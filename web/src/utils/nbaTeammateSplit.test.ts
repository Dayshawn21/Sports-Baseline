import { describe, expect, it } from 'vitest'
import type { NbaSplitTeammate, NbaTeammateSplit } from '~/types/nba'
import { activeTeammate, marketSplit, parseOutParam, splitSideText, teammateLabel } from '~/utils/nbaTeammateSplit'

function teammate(overrides: Partial<NbaSplitTeammate> = {}): NbaSplitTeammate {
  return {
    playerId: 5, espnAthleteId: '4433134', playerName: 'Anthony Edwards', status: 'Out', stale: false,
    firstTeamGameDate: '2025-10-22', sides: ['without', 'with', 'without', 'before'], ...overrides,
  }
}

const SPLIT: NbaTeammateSplit = {
  season: 2026,
  team: 'MIN',
  games: [
    { gameId: 4, gameDate: '2026-11-08', opponent: 'UTAH', values: { points: 24, double_double: 1 } },
    { gameId: 3, gameDate: '2026-11-06', opponent: 'DAL', values: { points: 10, double_double: 0 } },
    { gameId: 2, gameDate: '2026-11-04', opponent: 'PHX', values: { points: 16, double_double: 0 } },
    { gameId: 1, gameDate: '2026-11-02', opponent: 'LAL', values: { points: 30, double_double: 1 } },
  ],
  teammates: [teammate(), teammate({ playerId: 6, playerName: 'Donte DiVincenzo' })],
}

describe('parseOutParam', () => {
  it('reads digits only', () => {
    expect(parseOutParam(new URLSearchParams('out=322650'))).toBe(322650)
    expect(parseOutParam(new URLSearchParams('out=32a'))).toBeNull()
    expect(parseOutParam(new URLSearchParams('out='))).toBeNull()
    expect(parseOutParam(new URLSearchParams(''))).toBeNull()
  })
})

describe('activeTeammate', () => {
  it('finds a teammate listed tonight and ignores an unknown id', () => {
    expect(activeTeammate(6, SPLIT)?.playerName).toBe('Donte DiVincenzo')
    expect(activeTeammate(99, SPLIT)).toBeNull()
    expect(activeTeammate(5, null)).toBeNull()
    expect(activeTeammate(null, SPLIT)).toBeNull()
  })
})

describe('teammateLabel', () => {
  it('names the status and a stale report', () => {
    expect(teammateLabel(teammate())).toBe('Anthony Edwards (Out)')
    expect(teammateLabel(teammate({ status: 'Suspension', stale: true }))).toBe('Anthony Edwards (Suspension, stale report)')
  })
})

describe('marketSplit', () => {
  it('splits games, averages and overs by side, newest first', () => {
    const split = marketSplit(SPLIT, teammate(), 'points', 15.5)
    expect(split.with).toEqual({ games: [{ gameDate: '2026-11-06', opponent: 'DAL', value: 10 }], average: 10, over: 0, notLoaded: 0 })
    expect(split.without.games.map(game => game.value)).toEqual([24, 16])
    expect(split.without.average).toBe(20)
    expect(split.without.over).toBe(2)
    expect(split.before).toBe(1)
  })

  it('has no over count without a line', () => {
    expect(marketSplit(SPLIT, teammate(), 'points', null).without.over).toBeNull()
  })

  it('skips a stat that was not loaded and counts it', () => {
    const games = SPLIT.games.map(game => game.gameId === 4 ? { ...game, values: { points: null } } : game)
    const split = marketSplit({ ...SPLIT, games }, teammate(), 'points', 15.5)
    expect(split.without.games.map(game => game.value)).toEqual([16])
    expect(split.without.notLoaded).toBe(1)
  })

  it('counts double-double yeses whatever the line', () => {
    const split = marketSplit(SPLIT, teammate(), 'double_double', null)
    expect(split.without.over).toBe(1)
    expect(split.with.over).toBe(0)
  })

  it('leaves both sides empty for a teammate with no games on record', () => {
    const none = teammate({ firstTeamGameDate: null, sides: ['before', 'before', 'before', 'before'] })
    const split = marketSplit(SPLIT, none, 'points', 15.5)
    expect(split.with.games).toEqual([])
    expect(split.without.average).toBeNull()
    expect(split.before).toBe(4)
  })
})

describe('splitSideText', () => {
  it('reads games, average and overs', () => {
    const split = marketSplit(SPLIT, teammate(), 'points', 15.5)
    expect(splitSideText(split.without, 'points', 15.5)).toBe('2 games · 20 avg · 2 over 15.5')
    expect(splitSideText(split.with, 'points', 15.5)).toBe('1 game · 10 avg · 0 over 15.5')
    expect(splitSideText(split.with, 'points', null)).toBe('1 game · 10 avg')
  })

  it('reads double-double as yeses and an empty side as no games', () => {
    const split = marketSplit(SPLIT, teammate(), 'double_double', null)
    expect(splitSideText(split.without, 'double_double', null)).toBe('1 of 2 yes')
    const none = marketSplit(SPLIT, teammate({ sides: ['before', 'before', 'before', 'before'] }), 'points', 15.5)
    expect(splitSideText(none.without, 'points', 15.5)).toBe('No games')
  })
})
