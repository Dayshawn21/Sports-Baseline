import { describe, expect, it } from 'vitest'
import type { NbaLineOnlyLine, NbaPropBoardGame, NbaPropLine } from '~/types/nba'
import { NBA_LINE_ONLY_MARKETS, nbaLineOnlyGroups } from '~/utils/nbaLineOnly'
import { nbaBoardGameLabels, nbaBoardMarket, nbaBoardPath, nbaPropBoard } from '~/utils/nbaPropBoard'
import { parseSlateDate } from '~/utils/nbaSlate'
import { nbaPropGroups } from '~/utils/nbaProps'

function line(overrides: Partial<NbaPropLine> = {}): NbaPropLine {
  return {
    playerId: 1, playerName: 'Cade Cunningham', position: 'G', team: 'DET', market: 'assists',
    oddsType: 'standard', line: 9.5, fetchedAt: '2026-10-21T16:00:00Z',
    recent: [{ gameDate: '2026-10-20', opponent: 'NY', value: 0 }],
    projection: 8, gamesInSample: 20, priorMinutes: 30, gap: -1.5,
    pOver: 0.35, pUnder: 0.65, overProbabilityVersion: 'nba-pover-v1', flags: [],
    ...overrides,
  }
}

function other(overrides: Partial<NbaLineOnlyLine> = {}): NbaLineOnlyLine {
  return {
    playerId: 1, playerName: 'Cade Cunningham', position: 'G', team: 'DET', market: 'double_double',
    oddsType: 'standard', line: 0.5, fetchedAt: '2026-10-21T16:00:00Z', recent: [], ...overrides,
  }
}

function game(overrides: Partial<NbaPropBoardGame> = {}): NbaPropBoardGame {
  return {
    gameId: 1, awayTeam: 'DET', homeTeam: 'NY', startUtc: '2026-10-22T00:00:00Z',
    status: 'scheduled', lines: [line()], lineOnlyLines: [], ...overrides,
  }
}

function rows(games: NbaPropBoardGame[], market = 'assists') {
  return nbaPropBoard(games).find(group => group.market === market)!.rows
}

describe('nbaPropBoard', () => {
  it('reuses both game-page assemblers and keeps alternate rungs in one row', () => {
    const input = game({
      lines: [line({ line: 12.5, oddsType: 'demon', gap: -4.5 }), line()],
      lineOnlyLines: [other({ line: 1.5, oddsType: 'demon' }), other()],
    })
    expect(rows([input])[0].row).toEqual(nbaPropGroups(input.lines)[0].cards[0])
    expect(rows([input], 'double_double')[0].row).toEqual(nbaLineOnlyGroups(input.lineOnlyLines)[0].rows[0])
    expect(rows([input])).toHaveLength(1)
    expect(rows([input])[0].row.rungs).toHaveLength(2)
    expect(rows([input], 'double_double')).toHaveLength(1)
    expect(rows([input], 'double_double')[0].row.rungs).toHaveLength(2)
  })

  it('keeps the same player separate across games and kinds, preserving game context', () => {
    const games = [game({ lineOnlyLines: [other({ market: 'assists' })] }), game({ gameId: 2 })]
    const result = rows(games)
    expect(result).toHaveLength(3)
    expect(new Set(result.map(row => row.key)).size).toBe(3)
    expect(result.find(row => row.key === 'modelled:2:assists:1')?.game).toEqual({
      gameId: 2, awayTeam: 'DET', homeTeam: 'NY', startUtc: '2026-10-22T00:00:00Z', status: 'scheduled',
    })
  })

  it('orders by actual tip instant then name, with deterministic id ties', () => {
    const input = [
      game({ gameId: 3, lines: [line({ playerName: 'Aaron' })] }),
      game({ gameId: 2, lines: [line({ playerId: 2, playerName: 'Aaron' }), line({ playerName: 'Aaron' })] }),
      game({ gameId: 4, startUtc: '2026-10-21T18:00:00-05:00', lines: [line({ playerName: 'Zed' })] }),
      game({ gameId: 5, lines: [line({ playerName: 'Zed' })] }),
    ]
    expect(rows(input).map(row => [row.game.gameId, row.row.playerId])).toEqual([
      [4, 1], [2, 1], [2, 2], [3, 1], [5, 1],
    ])
  })

  it('never uses gap or probability to order rows', () => {
    const input = [game({ lines: [line({ playerName: 'Zed', playerId: 2 }), line({ playerName: 'Aaron' })] })]
    const before = rows(input).map(row => row.key)
    input[0].lines[0] = line({ playerName: 'Zed', playerId: 2, gap: 100, pOver: 1 })
    input[0].lines[1] = line({ playerName: 'Aaron', gap: -100, pOver: 0 })
    expect(rows(input).map(row => row.key)).toEqual(before)
  })

  it('places null and invalid tips last, retaining every game status', () => {
    const input = [
      game({ gameId: 1, startUtc: null, status: 'postponed' }),
      game({ gameId: 2, startUtc: 'invalid', status: 'canceled' }),
      game({ gameId: 3, status: 'completed' }),
    ]
    expect(rows(input).map(row => [row.game.gameId, row.game.status])).toEqual([
      [3, 'completed'], [1, 'postponed'], [2, 'canceled'],
    ])
  })

  it('retains null projections and actual zero probabilities and recent values', () => {
    const result = rows([game({ lines: [
      line({ projection: 0, gap: 0, pOver: 0, pUnder: 1 }),
      line({ playerId: 2, projection: null, gap: null, pOver: null, pUnder: null, flags: ['few_prior_games'] }),
    ] })])
    expect(result[0].row).toMatchObject({
      projectionRow: { projection: '0.0', gap: '0.0', pOver: '0%' }, recent: [{ value: 0 }],
    })
    expect(result[1].row).toMatchObject({ projectionRow: null, flagText: 'No projection: fewer than 10 earlier games' })
  })

  it('includes empty known markets in fixed order, followed by unknown returned markets', () => {
    expect(nbaPropBoard([])).toEqual(NBA_LINE_ONLY_MARKETS.map(market => ({ market, rows: [] })))
    const result = nbaPropBoard([game({ lines: [], lineOnlyLines: [other({ market: 'future_market' })] })])
    expect(result.map(group => group.market)).toEqual([...NBA_LINE_ONLY_MARKETS, 'future_market'])
    expect(result.at(-1)?.rows).toHaveLength(1)
    expect(nbaPropBoard([game({ lines: [] })]).every(group => group.rows.length === 0)).toBe(true)
  })

  it('does not mutate the response or its line arrays', () => {
    const input = [game({ lines: [line({ playerId: 2, playerName: 'Zed' }), line()] })]
    const original = structuredClone(input)
    nbaPropBoard(input)
    expect(input).toEqual(original)
  })
})

describe('nbaBoardGameLabels', () => {
  const now = new Date('2026-10-22T00:00:00Z')

  it('labels tip times explicitly in Central time, including daylight and standard time', () => {
    expect(nbaBoardGameLabels(game(), now)).toEqual({ tip: 'Wed 7:00 PM CT', status: 'Tipped off' })
    expect(nbaBoardGameLabels(game({ startUtc: '2026-12-02T00:00:00Z' }), now)).toEqual({
      tip: 'Tue 6:00 PM CT', status: null,
    })
  })

  it('gives terminal status precedence over an elapsed tip', () => {
    for (const [status, label] of [['completed', 'Final'], ['postponed', 'Postponed'], ['canceled', 'Canceled']]) {
      expect(nbaBoardGameLabels(game({ status }), now).status).toBe(label)
    }
    expect(nbaBoardGameLabels(game({ startUtc: '2026-10-21T23:59:00Z' }), now).status).toBe('Tipped off')
    expect(nbaBoardGameLabels(game({ startUtc: '2026-10-22T00:01:00Z' }), now).status).toBeNull()
  })

  it('labels missing or malformed tips without claiming the game has started', () => {
    for (const startUtc of [null, 'invalid']) {
      expect(nbaBoardGameLabels(game({ startUtc }), now)).toEqual({ tip: 'Tip time not set', status: null })
      expect(nbaBoardGameLabels(game({ startUtc, status: 'postponed' }), now).status).toBe('Postponed')
    }
  })
})

describe('board URL selection', () => {
  it('defaults absent, malformed or unavailable market values to Points, retaining empty known markets', () => {
    const groups = nbaPropBoard([])
    for (const value of [null, '', 'no-such-market', 'Assists']) {
      expect(nbaBoardMarket(value, groups)).toBe('points')
    }
    expect(nbaBoardMarket('assists', groups)).toBe('assists')
    const extended = nbaPropBoard([game({ lineOnlyLines: [other({ market: 'future_market' })] })])
    expect(nbaBoardMarket('future_market', extended)).toBe('future_market')
  })

  it('builds adjacent-date paths preserving and encoding the market, with no path for a missing date', () => {
    expect(nbaBoardPath('2026-10-22', 'assists')).toBe('/nba/board?date=2026-10-22&market=assists')
    expect(nbaBoardPath(null, 'points')).toBeNull()
    expect(nbaBoardPath('2026-10-22', 'custom + market')).toBe('/nba/board?date=2026-10-22&market=custom+%2B+market')
  })

  it('uses the slate date parser to reject invalid calendar dates without shifting a valid Eastern day', () => {
    expect(parseSlateDate('2026-10-21')).toBe('2026-10-21')
    for (const value of [null, '2026-02-30', '2026-13-01', '2026-10-21T00:00:00Z', 'bad']) {
      expect(parseSlateDate(value)).toBeNull()
    }
  })
})
