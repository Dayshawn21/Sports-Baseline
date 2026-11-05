import { describe, expect, it } from 'vitest'
import type { NhlLineOnlyLine, NhlLineOnlyMarket, NhlPropBoardGame } from '~/types/nhl'
import { nhlBoardGameStatus, nhlBoardMarket, nhlBoardPath, nhlPropBoard, type NhlBoardGameContext } from './nhlPropBoard'

const NOW = new Date('2026-10-24T20:00:00Z')

function line(overrides: Partial<NhlLineOnlyLine> = {}): NhlLineOnlyLine {
  return {
    provider: 'prizepicks', providerPropId: 'a', playerId: 1, playerName: 'Amy', position: 'C', team: 'TBL',
    market: 'shots_on_goal', oddsType: 'standard', line: 2.5, fetchedAt: '2026-10-24T12:00:00Z',
    projection: { modelVersion: 'nhl-reference-v1', value: null, gamesInSample: 0, gap: null, pOver: null, flags: ['few_prior_games'] }, ...overrides,
  }
}

function game(gameId: number, lines: NhlLineOnlyLine[], startUtc: string | null = '2026-10-25T00:00:00Z'): NhlPropBoardGame {
  return { gameId, awayTeam: 'TBL', homeTeam: 'CHI', startUtc, status: 'scheduled', lines }
}

const CONTEXT: NhlBoardGameContext = { gameId: 1, awayTeam: 'TBL', homeTeam: 'CHI', startUtc: '2026-10-25T00:00:00Z', status: 'scheduled' }

describe('nhlPropBoard', () => {
  it('lists every market, including those with no rows', () => {
    const groups = nhlPropBoard([game(1, [line()])])
    expect(groups).toHaveLength(12)
    expect(groups.find(group => group.market === 'hits')?.rows).toEqual([])
  })

  it('orders rows by puck drop, then player name, with unknown starts last', () => {
    const groups = nhlPropBoard([
      game(3, [line({ playerId: 5, playerName: 'Zed' })], null),
      game(2, [line({ playerId: 4, playerName: 'Zoe' })], '2026-10-25T01:00:00Z'),
      game(1, [line({ playerId: 2, playerName: 'Bo' }), line({ playerId: 1, playerName: 'Amy' })]),
    ])
    expect(groups[0].rows.map(item => item.row.playerName)).toEqual(['Amy', 'Bo', 'Zoe', 'Zed'])
  })

  it('keeps one player in two games as two rows', () => {
    const groups = nhlPropBoard([game(1, [line()]), game(2, [line()], '2026-10-25T02:00:00Z')])
    expect(groups[0].rows.map(item => item.key)).toEqual(['1:shots_on_goal:1', '2:shots_on_goal:1'])
  })

  it('groups one player\'s rungs into a single row with the standard line', () => {
    const groups = nhlPropBoard([game(1, [
      line({ providerPropId: 'a' }), line({ providerPropId: 'b', oddsType: 'demon', line: 4.5 }),
    ])])
    const [only] = groups[0].rows
    expect(only.row.standard).toBe('2.5')
    expect(only.row.rungs.map(rung => rung.oddsType)).toEqual(['standard', 'demon'])
  })

  it('does not carry the lines onto the game context', () => {
    expect(nhlPropBoard([game(1, [line()])])[0].rows[0].game).not.toHaveProperty('lines')
  })
})

describe('nhlBoardMarket', () => {
  const groups = nhlPropBoard([game(1, [line({ market: 'points' })])])

  it('keeps a requested market, even an empty one', () => {
    expect(nhlBoardMarket('hits', groups)).toBe('hits')
  })

  it('falls back to the first market with rows for a missing or unknown value', () => {
    const expected: NhlLineOnlyMarket = 'points'
    expect(nhlBoardMarket(null, groups)).toBe(expected)
    expect(nhlBoardMarket('nonsense', groups)).toBe(expected)
  })

  it('falls back to Shots on Goal when nothing has rows', () => {
    expect(nhlBoardMarket(null, nhlPropBoard([]))).toBe('shots_on_goal')
  })
})

describe('nhlBoardPath', () => {
  it('builds a dated, market-pinned path and is null without a date', () => {
    expect(nhlBoardPath('2026-10-24', 'power_play_points')).toBe('/nhl/board?date=2026-10-24&market=power_play_points')
    expect(nhlBoardPath(null, 'points')).toBeNull()
  })
})

describe('nhlBoardGameStatus', () => {
  it('labels terminal states and started games, and leaves upcoming or unknown starts blank', () => {
    expect(nhlBoardGameStatus({ ...CONTEXT, status: 'completed' }, NOW)).toBe('Final')
    expect(nhlBoardGameStatus({ ...CONTEXT, startUtc: '2026-10-24T19:00:00Z' }, NOW)).toBe('Started')
    expect(nhlBoardGameStatus(CONTEXT, NOW)).toBeNull()
    expect(nhlBoardGameStatus({ ...CONTEXT, startUtc: null }, NOW)).toBeNull()
  })
})
