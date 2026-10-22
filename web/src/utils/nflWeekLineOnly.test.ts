import { describe, expect, it } from 'vitest'
import type { NflLineOnlyBoardGame, NflLineOnlyLine, NflSlateGame } from '~/types/nfl'
import { availableNflPropGames, nflWeekLineOnlyCategories } from '~/utils/nflWeekLineOnly'

const NOW = new Date('2026-10-21T18:00:00Z')
const line: NflLineOnlyLine = {
  playerId: 1, playerName: 'Kicker', position: 'K', team: 'ATL', market: 'kicking_points',
  oddsType: 'standard', line: 7.5, fetchedAt: '2026-10-21T17:00:00Z', recent: [],
}
const game: NflLineOnlyBoardGame = {
  gameId: 1, startUtc: '2026-10-22T18:00:00Z', awayTeam: 'ATL', homeTeam: 'NO', lines: [line],
}

describe('weekly line-only markets', () => {
  it('includes games without modelled props and removes closed and empty games', () => {
    const games = [game, { ...game, gameId: 2, startUtc: NOW.toISOString() }, { ...game, gameId: 3, lines: [] }]
    expect(availableNflPropGames([], games, NOW).map(item => item.gameId)).toEqual([1])
    expect(nflWeekLineOnlyCategories(games, 'all', null, NOW)[0].games.map(item => item.game.gameId)).toEqual([1])
  })

  it('merges a game present in both feeds without duplicating it', () => {
    const modelled = { ...game, lines: [{ lineId: 1 }] } as unknown as NflSlateGame
    expect(availableNflPropGames([modelled], [game], NOW)).toHaveLength(1)
  })

  it('filters by game and position, and keeps each games player history separate', () => {
    const second = { ...game, gameId: 2, lines: [{ ...line, line: 9.5, recent: [{ season: 2026, week: 6, opponent: 'LV', value: 12 }] }] }
    expect(nflWeekLineOnlyCategories([game, second], 'QB', null, NOW)).toEqual([])
    const [category] = nflWeekLineOnlyCategories([game, second], 'K', 2, NOW)
    expect(category.count).toBe(1)
    expect(category.games[0].game.gameId).toBe(2)
    expect(category.games[0].group.rows[0]).toMatchObject({ count: 1, overCount: 1 })
    expect(nflWeekLineOnlyCategories([game], 'all', 999, NOW)).toEqual([])
  })

  it('counts player-market rows once and preserves standard and alternate rungs', () => {
    const games = [{ ...game, lines: [line, { ...line, line: 10.5, oddsType: 'demon' }] }]
    const [category] = nflWeekLineOnlyCategories(games, 'all', null, NOW)
    expect(category.count).toBe(1)
    expect(category.games[0].group.rows[0].rungs.map(rung => rung.line)).toEqual([7.5, 10.5])
  })

  it('orders the extra markets consistently and keeps targets on their reference path', () => {
    const games = [{ ...game, lines: [line, { ...line, market: 'passing_touchdowns', position: 'QB' }, { ...line, market: 'receiving_targets' }] }]
    expect(nflWeekLineOnlyCategories(games, 'all', null, NOW).map(item => item.market)).toEqual(['passing_touchdowns', 'kicking_points'])
    expect(nflWeekLineOnlyCategories([], 'all', null, NOW)).toEqual([])
  })
})
