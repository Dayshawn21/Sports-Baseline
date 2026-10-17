import { describe, expect, it } from 'vitest'
import type { NflSlateGame, NflSlateLine } from '~/types/nfl'
import { buildNflPropBoard, categoryReferenceLine, compareBoardLines, edgeShare, filterNflPropBoardGames, flattenSlateLines, isRateable, isUpcomingGame } from '~/utils/nflPropBoard'

const EMPTY_SAMPLE = { average: null, values: [] }

function line(lineId: number, overrides: Partial<NflSlateLine> = {}): NflSlateLine {
  return {
    lineId,
    playerId: lineId,
    playerName: `Player ${lineId}`,
    position: 'WR',
    opponentTeam: 'BUF',
    opponentPositionAverage: null,
    recentForm: EMPTY_SAMPLE,
    opponentHistory: EMPTY_SAMPLE,
    opponentAllowedHistory: EMPTY_SAMPLE,
    market: 'receiving_yards',
    segment: 'full_game',
    oddsType: 'standard',
    projection: 70,
    line: 60,
    edge: 10,
    gamesInSample: 8,
    baselineSeason: 2026,
    baselineReason: 'current_season',
    opponentAdjustmentPct: null,
    opponentSampleGames: null,
    usageAdjustmentPct: null,
    usageSampleGames: null,
    provider: 'prizepicks',
    fetchedAt: '2026-09-18T12:00:00Z',
    projectionModelVersion: 'opponent-dvp-usage-snap-v1',
    qualityFlags: [],
    bookProbability: null,
    bookProbabilityDevigged: null,
    bookCount: null,
    bookIncludesMargin: null,
    bookFetchedAt: null,
    injuryStatus: null,
    practiceStatus: null,
    injury: null,
    depthPosition: null,
    depthRank: null,
    previousDepthPosition: null,
    previousDepthRank: null,
    snapShare: null,
    snapShareGames: null,
    pOver: null,
    pUnder: null,
    overProbabilityVersion: null,
    ...overrides,
  }
}

function game(gameId: number, lines: NflSlateLine[], overrides: Partial<NflSlateGame> = {}): NflSlateGame {
  return {
    gameId,
    gameDate: '2099-09-20',
    startUtc: '2099-09-20T17:00:00Z',
    awayTeam: 'NYJ',
    homeTeam: 'MIA',
    status: 'scheduled',
    lines,
    odds: null,
    awayContext: null,
    homeContext: null,
    weather: { venueType: 'outdoor', forecastFor: null, temperatureF: null, windMph: null, windGustMph: null, precipitationProbability: null, fetchedAt: null },
    model: null,
    ...overrides,
  }
}

describe('categoryReferenceLine', () => {
  it('takes the median of the lines', () => {
    expect(categoryReferenceLine([{ line: 10 }, { line: 30 }, { line: 20 }])).toBe(20)
    expect(categoryReferenceLine([{ line: 10 }, { line: 30 }])).toBe(20)
  })

  it('ignores missing and zero lines, and is null with nothing usable', () => {
    expect(categoryReferenceLine([{ line: null }, { line: 0 }, { line: 40 }])).toBe(40)
    expect(categoryReferenceLine([{ line: null }])).toBeNull()
    expect(categoryReferenceLine([])).toBeNull()
  })

  it('is not dragged by a tiny outlier the way a mean would be', () => {
    expect(categoryReferenceLine([{ line: 0.5 }, { line: 26 }, { line: 27 }, { line: 28 }, { line: 29 }])).toBe(27)
  })
})

describe('edgeShare', () => {
  it('divides the edge by the category reference, not the row line', () => {
    expect(edgeShare({ edge: 12 }, 60)).toBeCloseTo(0.2)
    expect(edgeShare({ edge: -3 }, 60)).toBeCloseTo(-0.05)
  })

  it('keeps a tiny line from exploding, because the denominator is shared', () => {
    // A blocking tight end's 0.5-yard line projected at 12.1 against a 26.5 category median.
    expect(edgeShare({ edge: 11.6 }, 26.5)).toBeCloseTo(0.438, 2)
  })

  it('returns null without an edge or a usable reference', () => {
    expect(edgeShare({ edge: null }, 60)).toBeNull()
    expect(edgeShare({ edge: 12 }, null)).toBeNull()
    expect(edgeShare({ edge: 12 }, 0)).toBeNull()
  })
})

describe('isRateable', () => {
  const base = { edge: 10, gamesInSample: 8, line: 60, market: 'receiving_yards', oddsType: 'standard', segment: 'full_game' }

  it('accepts a standard full-game line with enough sample', () => {
    expect(isRateable(base)).toBe(true)
  })

  it.each([
    ['no edge', { edge: null }],
    ['no line', { line: null }],
    ['alternate payout', { oddsType: 'goblin' }],
    ['partial segment', { segment: 'first_half' }],
    ['thin sample', { gamesInSample: 3 }],
    ['anytime TD, until 25c', { market: 'anytime_touchdown', edge: -0.13, line: 0.5 }],
  ])('rejects %s', (_label, override) => {
    expect(isRateable({ ...base, ...override })).toBe(false)
  })
})

describe('compareBoardLines', () => {
  const row = (lineId: number, edge: number, overrides: Partial<NflSlateLine> = {}) =>
    line(lineId, { edge, ...overrides })

  it('ranks by raw edge against the shared reference, so a tiny line cannot jump the board', () => {
    const tinyLine = row(1, 11.6, { line: 0.5 })
    const bigEdge = row(2, 20)
    // Against its own 0.5 line the first row reads as +2320%; against the category's it is behind.
    expect([tinyLine, bigEdge].sort(compareBoardLines(26.5)).map(item => item.lineId)).toEqual([2, 1])
  })

  it('ranks unders alongside overs by magnitude', () => {
    const under = row(1, -20)
    const over = row(2, 10)
    expect([over, under].sort(compareBoardLines(60)).map(item => item.lineId)).toEqual([1, 2])
  })

  it('drops ruled-out players below everything, whatever the edge', () => {
    const out = row(1, 40, { qualityFlags: ['injury_out'] })
    const doubtful = row(2, 30, { qualityFlags: ['injury_doubtful'] })
    const clear = row(3, 2)
    expect([out, doubtful, clear].sort(compareBoardLines(60)).map(item => item.lineId)).toEqual([3, 2, 1])
  })

  it('drops a thin sample below a full one, however extreme the edge', () => {
    const thin = row(1, -120, { gamesInSample: 4 })
    const full = row(2, 10, { gamesInSample: 14 })
    expect([thin, full].sort(compareBoardLines(60)).map(item => item.lineId)).toEqual([2, 1])
  })

  it('weighs availability above sample depth', () => {
    const outButDeep = row(1, 30, { gamesInSample: 17, qualityFlags: ['injury_out'] })
    const thinButActive = row(2, 5, { gamesInSample: 4 })
    expect([outButDeep, thinButActive].sort(compareBoardLines(60)).map(item => item.lineId)).toEqual([2, 1])
  })

  it('demotes a stale baseline below a current one', () => {
    const stale = row(1, 30, { qualityFlags: ['stale_baseline_season'] })
    const current = row(2, 5)
    expect([stale, current].sort(compareBoardLines(60)).map(item => item.lineId)).toEqual([2, 1])
  })

  it('breaks ties on player name then line id', () => {
    const later = line(2, { playerName: 'Zane Adams' })
    const earlier = line(1, { playerName: 'Adam Zane' })
    expect([later, earlier].sort(compareBoardLines(60)).map(item => item.lineId)).toEqual([1, 2])
  })
})

describe('flattenSlateLines', () => {
  it('attaches game context to every line', () => {
    const flat = flattenSlateLines([
      game(10, [line(1)]),
      game(11, [line(2)], { awayTeam: 'KC', homeTeam: 'DEN' }),
    ])
    expect(flat.map(item => [item.lineId, item.gameId, item.awayTeam, item.homeTeam])).toEqual([
      [1, 10, 'NYJ', 'MIA'],
      [2, 11, 'KC', 'DEN'],
    ])
  })
})

describe('isUpcomingGame', () => {
  const now = new Date('2026-09-21T18:00:00Z')

  it('hides games at or before kickoff and retains future or unknown times', () => {
    expect(isUpcomingGame(game(1, [], { startUtc: '2026-09-21T18:00:00Z' }), now)).toBe(false)
    expect(isUpcomingGame(game(2, [], { startUtc: '2026-09-21T18:00:01Z' }), now)).toBe(true)
    expect(isUpcomingGame(game(3, [], { startUtc: null }), now)).toBe(true)
  })
})

describe('filterNflPropBoardGames', () => {
  const now = new Date('2026-09-21T18:00:00Z')
  const games = [
    game(1, [line(1)], { startUtc: '2026-09-21T18:00:01Z' }),
    game(2, [line(2)], { startUtc: '2026-09-21T19:00:00Z' }),
    game(3, [line(3)], { startUtc: '2026-09-21T17:59:59Z' }),
    game(4, [], { startUtc: '2026-09-21T20:00:00Z' }),
  ]

  it('returns every upcoming game with prop lines for All games', () => {
    expect(filterNflPropBoardGames(games, null, now).map(item => item.gameId)).toEqual([1, 2])
  })

  it('narrows the upcoming slate to one selected game', () => {
    expect(filterNflPropBoardGames(games, 2, now).map(item => item.gameId)).toEqual([2])
    expect(filterNflPropBoardGames(games, 3, now)).toEqual([])
  })
})

describe('buildNflPropBoard', () => {
  it('excludes lines from games that have already kicked off', () => {
    const board = buildNflPropBoard([
      game(10, [line(1)], { startUtc: '2026-09-21T17:59:59Z' }),
      game(11, [line(2)], { startUtc: '2026-09-21T18:00:01Z' }),
    ], 'all', new Date('2026-09-21T18:00:00Z'))
    expect(board[0].rateable.map(item => item.lineId)).toEqual([2])
  })

  it('buckets lines by market across games, in label order', () => {
    const board = buildNflPropBoard([
      game(10, [line(1, { market: 'receptions' }), line(2, { market: 'passing_yards', position: 'QB' })]),
      game(11, [line(3, { market: 'receptions' })]),
    ], 'all')
    expect(board.map(category => [category.market, category.rateable.length])).toEqual([
      ['passing_yards', 1],
      ['receptions', 2],
    ])
  })

  it('splits rateable lines from alternate and partial ones', () => {
    const board = buildNflPropBoard([
      game(10, [
        line(1),
        line(2, { playerId: 2, segment: 'first_half' }),
        line(3, { playerId: 3, gamesInSample: 2 }),
      ]),
    ], 'all')
    expect(board[0].rateable.map(item => item.lineId)).toEqual([1])
    expect(board[0].other.map(item => item.lineId)).toEqual([2, 3])
  })

  it('collapses a player alternate line into the standard one', () => {
    const board = buildNflPropBoard([
      game(10, [line(1), line(2, { playerId: 1, oddsType: 'goblin', line: 45 })]),
    ], 'all')
    expect(board[0].rateable.map(item => item.lineId)).toEqual([1])
    expect(board[0].other).toEqual([])
  })

  it('scores each category against its own median rateable line', () => {
    const board = buildNflPropBoard([
      game(10, [
        line(1, { playerId: 1, line: 0.5, projection: 12.1, edge: 11.6 }),
        line(2, { playerId: 2, line: 26.5, projection: 46.5, edge: 20 }),
        line(3, { playerId: 3, line: 40, projection: 45, edge: 5 }),
      ]),
    ], 'all')
    expect(board[0].referenceLine).toBe(26.5)
    // The 0.5-yard line would lead on its own denominator; on the category's it does not.
    expect(board[0].rateable.map(item => item.lineId)).toEqual([2, 1, 3])
  })

  it('keeps Anytime TD out of the rated picks and ranks it by model probability', () => {
    const board = buildNflPropBoard([
      game(10, [
        line(1, { market: 'anytime_touchdown', projection: 0.28, edge: null }),
        line(2, { market: 'anytime_touchdown', projection: 0.46, edge: null }),
      ]),
    ], 'all')
    expect(board[0].rateable).toEqual([])
    expect(board[0].other.map(item => item.lineId)).toEqual([2, 1])
  })

  it('falls back to the unrateable lines for a reference when nothing is rateable', () => {
    const board = buildNflPropBoard([
      game(10, [line(1, { line: 30, segment: 'first_half' })]),
    ], 'all')
    expect(board[0].rateable).toEqual([])
    expect(board[0].referenceLine).toBe(30)
  })

  it('applies the position filter before bucketing', () => {
    const board = buildNflPropBoard([
      game(10, [line(1, { position: 'QB', market: 'passing_yards' }), line(2, { position: 'WR' })]),
    ], 'QB')
    expect(board.map(category => category.market)).toEqual(['passing_yards'])
  })

  it('keeps an unlabelled market, sorted after the known ones', () => {
    const board = buildNflPropBoard([
      game(10, [line(1, { market: 'kicking_points' }), line(2, { market: 'receptions' })]),
    ], 'all')
    expect(board.map(category => category.market)).toEqual(['receptions', 'kicking_points'])
  })
})
