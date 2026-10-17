import { describe, expect, it } from 'vitest'
import type { NflSlateGame, NflSlateLine } from '~/types/nfl'
import { gameBoardAsOf, nflGameProps } from '~/utils/nflGameProps'
import { buildNflPropBoard } from '~/utils/nflPropBoard'

const EMPTY_SAMPLE = { average: null, values: [] }
const BEFORE = new Date('2026-09-20T12:00:00Z')
const AFTER = new Date('2026-09-21T12:00:00Z')

function line(lineId: number, overrides: Partial<NflSlateLine> = {}): NflSlateLine {
  return {
    lineId, playerId: lineId, playerName: `Player ${lineId}`, position: 'WR', opponentTeam: 'BUF',
    opponentPositionAverage: null, recentForm: EMPTY_SAMPLE, opponentHistory: EMPTY_SAMPLE, opponentAllowedHistory: EMPTY_SAMPLE,
    market: 'receiving_yards', segment: 'full_game', oddsType: 'standard', projection: 70, line: 60, edge: 10,
    gamesInSample: 8, baselineSeason: 2026, baselineReason: 'current_season', opponentAdjustmentPct: null,
    opponentSampleGames: null, usageAdjustmentPct: null, usageSampleGames: null, provider: 'prizepicks',
    fetchedAt: '2026-09-18T12:00:00Z', projectionModelVersion: 'v', qualityFlags: [], bookProbability: null,
    bookProbabilityDevigged: null, bookCount: null, bookIncludesMargin: null, bookFetchedAt: null, injuryStatus: null,
    practiceStatus: null, injury: null, depthPosition: null, depthRank: null, previousDepthPosition: null,
    previousDepthRank: null, snapShare: null, snapShareGames: null, pOver: null, pUnder: null, overProbabilityVersion: null,
    ...overrides,
  }
}

function game(gameId: number, startUtc: string | null, lines: NflSlateLine[]): NflSlateGame {
  return {
    gameId, gameDate: '2026-09-20', startUtc, awayTeam: 'NYJ', homeTeam: 'MIA', status: 'scheduled', lines,
    odds: null, awayContext: null, homeContext: null, model: null,
    weather: { venueType: 'outdoor', forecastFor: null, temperatureF: null, windMph: null, windGustMph: null, precipitationProbability: null, fetchedAt: null },
  }
}

// Game 1 kicks off first; game 2 holds the biggest edge of the week.
const WEEK = [
  game(1, '2026-09-20T17:00:00Z', [line(11, { edge: 5 }), line(12, { edge: 2, position: 'RB', market: 'rushing_yards' })]),
  game(2, '2026-09-21T00:20:00Z', [line(21, { edge: 30 }), line(22, { edge: 8 })]),
]

describe('nflGameProps', () => {
  it('ranks an upcoming game by the week-wide board', () => {
    const receiving = nflGameProps(WEEK, 1, 'all', 'full_game', BEFORE).find(item => item.category.market === 'receiving_yards')
    const board = buildNflPropBoard(WEEK, 'all', BEFORE).find(item => item.market === 'receiving_yards')
    expect(receiving?.rateable.map(item => [item.row.lineId, item.rank])).toEqual([[11, 3]])
    expect(board?.rateable[2].lineId).toBe(11)
    expect(receiving?.category.referenceLine).toBe(board?.referenceLine)
  })

  it('keeps a started game its cards and the ranks from just before its kickoff', () => {
    expect(buildNflPropBoard(WEEK, 'all', AFTER).flatMap(item => item.rateable)).toEqual([])
    const markets = nflGameProps(WEEK, 1, 'all', 'full_game', AFTER)
    // Prop-board market order, which is MARKET_LABELS order.
    expect(markets.map(item => item.category.market)).toEqual(['rushing_yards', 'receiving_yards'])
    expect(markets[1].rateable[0].rank).toBe(3)
  })

  it('filters by position and drops markets left empty', () => {
    const markets = nflGameProps(WEEK, 1, 'RB', 'full_game', BEFORE)
    expect(markets.map(item => item.category.market)).toEqual(['rushing_yards'])
  })

  it('shows only the chosen period, where partial-game lines are never rateable', () => {
    const withHalf = [game(1, '2026-09-20T17:00:00Z', [line(11), line(13, { segment: 'first_half', line: 30 })])]
    const [half] = nflGameProps(withHalf, 1, 'all', 'first_half', BEFORE)
    expect(half.rateable).toEqual([])
    expect(half.other.map(row => row.lineId)).toEqual([13])
    expect(nflGameProps(withHalf, 1, 'all', 'q1', BEFORE)).toEqual([])
  })

  it('is empty for an unknown game or one without lines', () => {
    expect(nflGameProps(WEEK, 99, 'all', 'full_game', BEFORE)).toEqual([])
    expect(nflGameProps([game(3, null, [])], 3, 'all', 'full_game', BEFORE)).toEqual([])
  })
})

describe('gameBoardAsOf', () => {
  it('is now before kickoff, a millisecond before kickoff after it, and now when kickoff is unknown', () => {
    const kickoff = '2026-09-20T17:00:00Z'
    expect(gameBoardAsOf({ startUtc: kickoff }, BEFORE)).toEqual(BEFORE)
    expect(gameBoardAsOf({ startUtc: kickoff }, AFTER).getTime()).toBe(Date.parse(kickoff) - 1)
    expect(gameBoardAsOf({ startUtc: null }, AFTER)).toEqual(AFTER)
  })
})
