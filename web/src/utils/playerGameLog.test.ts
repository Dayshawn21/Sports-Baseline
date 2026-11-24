import { describe, expect, it } from 'vitest'
import { playerFormAverages, playerGameLog } from '~/utils/playerGameLog'

const markets = [
  { market: 'rebounds', recent: [{ gameDate: '2026-11-07', opponent: 'TOR', value: 6 }, { gameDate: '2026-11-03', opponent: 'BOS', value: 2 }] },
  { market: 'points', recent: [{ gameDate: '2026-11-07', opponent: 'TOR', value: 18 }, { gameDate: '2026-11-05', opponent: null, value: null }] },
  { market: 'points_rebounds', recent: [{ gameDate: '2026-11-07', opponent: 'TOR', value: 24 }] },
]

describe('playerGameLog', () => {
  it('joins markets by date, newest first, in the given column order, leaving other markets out', () => {
    expect(playerGameLog(markets, ['points', 'rebounds', 'assists'])).toEqual({
      columns: ['points', 'rebounds'],
      rows: [
        { gameDate: '2026-11-07', opponent: 'TOR', values: [18, 6] },
        { gameDate: '2026-11-05', opponent: null, values: [null, null] },
        { gameDate: '2026-11-03', opponent: 'BOS', values: [null, 2] },
      ],
    })
  })

  it('keeps the newest games up to the limit', () => {
    expect(playerGameLog(markets, ['rebounds'], 1).rows).toEqual([{ gameDate: '2026-11-07', opponent: 'TOR', values: [6] }])
  })

  it('is empty without matching markets', () => {
    expect(playerGameLog([], ['points'])).toEqual({ columns: [], rows: [] })
  })
})

describe('playerFormAverages', () => {
  it('averages each column over the games that have a value', () => {
    expect(playerFormAverages(playerGameLog(markets, ['points', 'rebounds']))).toEqual([
      { market: 'points', average: 18, games: 1 }, { market: 'rebounds', average: 4, games: 2 },
    ])
  })
})
