import { describe, expect, it } from 'vitest'
import { boardStartTime, compareBoardRows, propBoardPath } from '~/utils/propBoardRows'

function entry(startUtc: string | null, playerName: string, gameId = 1, playerId = 1) {
  return { game: { gameId, startUtc }, row: { playerName, playerId } }
}

describe('boardStartTime', () => {
  it('reads a start and sends a missing or bad one last', () => {
    expect(boardStartTime('2026-11-16T23:00:00Z')).toBe(Date.parse('2026-11-16T23:00:00Z'))
    expect(boardStartTime(null)).toBe(Infinity)
    expect(boardStartTime('soon')).toBe(Infinity)
  })
})

describe('compareBoardRows', () => {
  it('orders by start, then name, then game and player id', () => {
    const rows = [
      entry(null, 'Aaron'),
      entry('2026-11-17T01:00:00Z', 'Aaron'),
      entry('2026-11-17T00:00:00Z', 'Zed'),
      entry('2026-11-17T00:00:00Z', 'Ben', 4, 2),
      entry('2026-11-17T00:00:00Z', 'Ben', 3, 9),
      entry('2026-11-17T00:00:00Z', 'Ben', 3, 1),
    ]
    expect([...rows].sort(compareBoardRows)).toEqual([rows[5], rows[4], rows[3], rows[2], rows[1], rows[0]])
  })
})

describe('propBoardPath', () => {
  it('builds each sport board link and needs a date', () => {
    expect(propBoardPath('nba', '2026-11-16', 'points')).toBe('/nba/props?date=2026-11-16&market=points')
    expect(propBoardPath('nhl', '2026-11-16', 'shots_on_goal')).toBe('/nhl/props?date=2026-11-16&market=shots_on_goal')
    expect(propBoardPath('nba', null, 'points')).toBeNull()
  })
})
