import { describe, expect, it } from 'vitest'
import type { NflHistorySample, NflSlateGame, NflSlateLine, NflSlateResponse, NflSlateWire } from '~/types/nfl'
import { expandNflSlate } from '~/utils/nflSlateWire'

const sample = (...values: number[]): NflHistorySample => ({
  average: values.reduce((a, b) => a + b, 0) / values.length,
  values: values.map((value, i) => ({ value, opponentTeam: 'NYJ', gameDate: `2026-09-0${i + 1}` })),
})
const FORM = sample(60, 70)
const LONG = sample(60, 70, 80)
const OPP = sample(55)
const ALLOWED = sample(45.5)

function line(lineId: number, overrides: Partial<NflSlateLine> = {}): NflSlateLine {
  return {
    lineId, playerId: 7, playerName: 'Player 7', position: 'WR', opponentTeam: 'BUF', opponentPositionAverage: null,
    recentForm: FORM, recentFormLong: LONG, opponentHistory: OPP, opponentAllowedHistory: ALLOWED,
    market: 'receiving_yards', segment: 'full_game', oddsType: 'standard', projection: 70, line: 60, edge: 10,
    gamesInSample: 8, baselineSeason: 2026, baselineReason: 'current_season', opponentAdjustmentPct: null,
    opponentSampleGames: null, usageAdjustmentPct: null, usageSampleGames: null, provider: 'prizepicks',
    fetchedAt: '2026-09-18T12:00:00Z', projectionModelVersion: 'v4', qualityFlags: [], bookProbability: null,
    bookProbabilityDevigged: null, bookCount: null, bookIncludesMargin: null, bookFetchedAt: null, injuryStatus: null,
    practiceStatus: null, injury: null, depthPosition: null, depthRank: null, previousDepthPosition: null,
    previousDepthRank: null, snapShare: null, snapShareGames: null, pOver: null, pUnder: null, overProbabilityVersion: null,
    ...overrides,
  }
}

function game(gameId: number, lines: NflSlateLine[]): NflSlateGame {
  return {
    gameId, gameDate: '2026-09-20', startUtc: '2026-09-20T17:00:00Z', awayTeam: 'NYJ', homeTeam: 'MIA', status: 'scheduled',
    lines, odds: null, awayContext: null, homeContext: null, model: null,
    weather: { venueType: 'outdoor', forecastFor: null, temperatureF: null, windMph: null, windGustMph: null, precipitationProbability: null, fetchedAt: null },
  }
}

function slate(games: NflSlateGame[]): NflSlateResponse {
  return { season: 2026, week: 9, gameCount: games.length, lineCount: 0, unmatchedCount: 0, games, unmatched: [] }
}

// What the API sends for `slate` (FORM=0, LONG=1, OPP=2, ALLOWED=3, line 20's form=4).
const FULL = slate([
  game(1, [line(10, { oddsType: 'demon' }), line(11, { oddsType: 'goblin' }), line(20, { recentForm: sample(12) })]),
  game(2, []),
])
const { recentFormLong: _unused, ...withoutLong } = line(30)
const WIRE: NflSlateWire = {
  ...FULL,
  games: [
    { ...game(1, []), lines: [
      { ...line(10, { oddsType: 'demon' }), recentForm: 0, recentFormLong: 1, opponentHistory: 2, opponentAllowedHistory: 3 },
      { ...line(11, { oddsType: 'goblin' }), recentForm: 0, recentFormLong: 1, opponentHistory: 2, opponentAllowedHistory: 3 },
      { ...line(20), recentForm: 4, recentFormLong: 1, opponentHistory: 2, opponentAllowedHistory: 3 },
    ] },
    { ...game(2, []), lines: [] },
  ],
  samples: [FORM, LONG, OPP, ALLOWED, sample(12)],
}

describe('expandNflSlate', () => {
  it('puts every line\'s history samples back', () => {
    expect(expandNflSlate(WIRE)).toEqual(FULL)
  })

  it('drops the samples list once it is used', () => {
    expect('samples' in expandNflSlate(WIRE)).toBe(false)
  })

  it('passes a copy stored before the change through unchanged', () => {
    expect(expandNflSlate(FULL)).toBe(FULL)
  })

  it('leaves a missing long window absent, as old copies had it', () => {
    const wire: NflSlateWire = {
      ...WIRE,
      games: [{ ...game(3, []), lines: [{ ...withoutLong, recentForm: 0, recentFormLong: null, opponentHistory: 2, opponentAllowedHistory: 3 }] }],
    }

    const expanded = expandNflSlate(wire).games[0].lines[0]

    expect(expanded.recentFormLong).toBeUndefined()
    expect(expanded.recentForm).toEqual(FORM)
  })

  it('fails loudly on an index past the samples rather than showing an empty history', () => {
    const wire: NflSlateWire = { ...WIRE, samples: WIRE.samples.slice(0, 2) }

    expect(() => expandNflSlate(wire)).toThrow(/history sample 2/)
  })
})
