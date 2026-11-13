import { describe, expect, it } from 'vitest'
import type { NflGameModel, NflSlateGame, NflSlateLine } from '~/types/nfl'
import { formatKickoffTime } from '~/utils/nflLabels'
import { history, nflProjectionHero, nflPropDetail } from '~/utils/nflPropDetail'

const EMPTY_SAMPLE = { average: null, values: [] }
const NOW = Date.parse('2026-09-30T12:00:00Z')
const KICKOFF = '2026-10-02T00:15:00Z'

function row(overrides: Partial<NflSlateLine> = {}): NflSlateLine {
  return {
    lineId: 7,
    playerId: 7,
    playerName: 'Jerry Jeudy',
    position: 'WR',
    opponentTeam: 'PIT',
    opponentPositionAverage: 34.6,
    recentForm: EMPTY_SAMPLE,
    opponentHistory: EMPTY_SAMPLE,
    opponentAllowedHistory: EMPTY_SAMPLE,
    market: 'receiving_yards',
    segment: 'full_game',
    oddsType: 'standard',
    projection: 39.1,
    line: 13.5,
    edge: 25.61,
    gamesInSample: 17,
    baselineSeason: 2025,
    baselineReason: 'previous_season',
    opponentAdjustmentPct: 9.4,
    opponentSampleGames: 168,
    usageAdjustmentPct: 8,
    usageSampleGames: 4,
    provider: 'prizepicks',
    fetchedAt: '2026-09-29T12:00:00Z',
    projectionModelVersion: 'opponent-dvp-tg-blend-usage-snap-v4',
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

const MODEL: NflGameModel = {
  modelVersion: 'nfl-elo-v1',
  homeElo: 1443,
  awayElo: 1531,
  homeWinProbability: 0.4425,
  homeSpread: 1.61,
  total: 37.2,
  marketHomeWinProbability: 0.43,
}

function game(overrides: Partial<NflSlateGame> = {}): NflSlateGame {
  return {
    gameId: 49,
    gameDate: '2026-10-01',
    startUtc: KICKOFF,
    awayTeam: 'PIT',
    homeTeam: 'CLE',
    status: 'scheduled',
    lines: [],
    odds: { book: 'draftkings', homeMoneyline: 124, awayMoneyline: -148, homeSpread: 2.5, total: 38.5 },
    awayContext: null,
    homeContext: null,
    weather: { venueType: 'outdoor', forecastFor: null, temperatureF: null, windMph: null, windGustMph: null, precipitationProbability: null, fetchedAt: null },
    model: MODEL,
    ...overrides,
  }
}

describe('nflPropDetail header', () => {
  it('names the player team from the game and builds the meta line', () => {
    const detail = nflPropDetail(row(), game(), [], NOW)
    expect(detail.badge).toBe('CLE')
    expect(detail.meta).toBe(`WR · Receiving yards · PIT @ CLE · ${formatKickoffTime(KICKOFF)}`)
    expect(detail.projectionLabel).toBe('Projected receiving yards')
  })

  it('adds a non-full-game segment', () => {
    expect(nflPropDetail(row({ segment: 'first_half' }), game(), [], NOW).meta).toMatch(/ · 1st half$/i)
  })

  it('falls back to the position and drops matchup and kickoff without a game', () => {
    const detail = nflPropDetail(row(), null, [], NOW)
    expect(detail.badge).toBe('WR')
    expect(detail.meta).toBe('WR · Receiving yards')
  })
})

describe('nflPropDetail projection', () => {
  it('reads an OVER edge against the line', () => {
    const detail = nflPropDetail(row(), game(), [], NOW)
    expect(detail.projectionText).toBe('39.1')
    expect(detail.deltaText).toBe('+25.6 vs 13.5 line')
    expect(detail).toMatchObject({ isUnder: false, hasEdge: true })
  })

  it('reads an UNDER edge', () => {
    const detail = nflPropDetail(row({ projection: 192.4, line: 212.5, edge: -20.12 }), game(), [], NOW)
    expect(detail.deltaText).toBe('-20.1 vs 212.5 line')
    expect(detail).toMatchObject({ isUnder: true, hasEdge: true })
  })

  it('shows only the line when there is no edge, and no line when there is none', () => {
    const td = nflPropDetail(row({ market: 'anytime_touchdown', projection: 0.11, line: 0.5, edge: null }), game(), [], NOW)
    expect(td.projectionText).toBe('11.0%')
    expect(td.deltaText).toBe('0.5 line')
    expect(td).toMatchObject({ isUnder: false, hasEdge: false })
    expect(nflPropDetail(row({ line: null, edge: null, projection: null }), game(), [], NOW)).toMatchObject({ deltaText: 'No line', projectionText: '--' })
  })

  it('keeps the old panel reason sentence, opponent adjustment included', () => {
    expect(nflPropDetail(row(), game(), [], NOW).why).toMatch(/^Model 39\.1 vs 13\.5 line.*\. Opponent adjustment: \+9\.4%\.$/)
    expect(nflPropDetail(row({ opponentAdjustmentPct: null }), game(), [], NOW).why).not.toContain('Opponent adjustment')
  })
})

describe('nflPropDetail history', () => {
  it('formats averages and values as the old panel did', () => {
    const detail = nflPropDetail(row({
      recentForm: { average: 21.8, values: [{ value: 0, opponentTeam: 'TB' }, { value: 26, opponentTeam: null }] },
    }), game(), [], NOW)
    expect(detail.recentForm).toEqual({ title: 'Recent form', value: '21.8 avg · 2 games', detail: '0.0 vs TB · 26.0 vs --', games: ['0.0 vs TB', '26.0 vs --'] })
    expect(detail.context.map(item => item.title)).toEqual(['Vs PIT', 'PIT allowed to all WRs, per game · last 5'])
    expect(detail.context[0]).toEqual({ title: 'Vs PIT', value: 'No completed history', detail: null, games: [] })
  })

  it('reads TD history as TD or No TD', () => {
    const detail = nflPropDetail(row({ market: 'anytime_touchdown', recentForm: { average: 0.2, values: [{ value: 1, opponentTeam: 'TB' }, { value: 0, opponentTeam: 'JAX' }] } }), game(), [], NOW)
    expect(detail.recentForm.detail).toBe('TD vs TB · No TD vs JAX')
    expect(detail.recentForm.games).toEqual(['TD vs TB', 'No TD vs JAX'])
  })

  it('lists each game once with its date when the sample has one', () => {
    const detail = nflPropDetail(row({ market: 'anytime_touchdown', recentForm: { average: 0.5, values: [{ value: 1, opponentTeam: 'TB', gameDate: '2020-10-04' }, { value: 0, opponentTeam: 'JAX' }] } }), game(), [], NOW)
    expect(detail.recentForm.games).toEqual(["TD vs TB (Oct 4 '20)", 'No TD vs JAX'])
  })

  it('reads the season from the passed now, not the wall clock', () => {
    const sample = { average: 26, values: [{ value: 26, opponentTeam: 'TB', gameDate: '2020-10-04' }] }
    expect(history('Recent form', 'receiving_yards', sample, new Date(2021, 0, 10)).games).toEqual(['26.0 vs TB (Oct 4)'])
  })
})

describe('nflPropDetail breakdown', () => {
  it('lists baseline, matchup, usage and the projection', () => {
    const [baseline, matchup, usage, projection, ...rest] = nflPropDetail(row(), game(), [], NOW).breakdown
    expect(baseline).toMatchObject({ label: 'Baseline', value: '17 games · 2025' })
    expect(baseline.note).toContain('most recent earlier season')
    expect(matchup).toEqual({ label: 'Matchup', value: 'PIT +9.4%', note: '34.6 allowed · 168 games' })
    expect(usage).toMatchObject({ label: 'Usage', value: '+8.0%' })
    expect(projection).toMatchObject({ label: 'Projection', value: '39.1' })
    expect(rest).toEqual([])
  })

  it('handles an unknown reason and missing adjustments', () => {
    const [baseline, matchup, usage] = nflPropDetail(row({ baselineReason: 'mystery', opponentAdjustmentPct: null, usageAdjustmentPct: null }), game(), [], NOW).breakdown
    expect(baseline.note).toBeNull()
    expect(matchup).toEqual({ label: 'Matchup', value: 'Unavailable', note: null })
    expect(usage.value).toBe('Not applicable')
  })

  it('adds snap share only where the line carries one', () => {
    const td = nflPropDetail(row({ market: 'anytime_touchdown', snapShare: 0.295, snapShareGames: 31 }), game(), [], NOW)
    expect(td.breakdown.find(item => item.label === 'Snap share')?.value).toBe('30% · 31 g, season-weighted')
  })
})

describe('nflPropDetail lines', () => {
  it('puts the selected line first, then alternates in order with their P(over)', () => {
    const detail = nflPropDetail(row({ pOver: 0.677, pUnder: 0.323 }), game(), [
      row({ lineId: 8, oddsType: 'goblin', line: 4.5, pOver: 0.76 }),
      row({ lineId: 9, oddsType: 'demon', line: 83.5, pOver: null }),
      row({ lineId: 10, oddsType: null, line: 20.5 }),
    ], NOW)
    expect(detail.lines.map(line => [line.key, line.typeLabel, line.lineText, line.pOverText, line.selected])).toEqual([
      [7, 'Standard', '13.5', '68% over', true],
      [8, 'Goblin', '4.5', '76% over', false],
      [9, 'Demon', '83.5', null, false],
      [10, 'Alternate', '20.5', null, false],
    ])
    expect(detail.pOverNote).toBe('Over 68% · Under 32%')
  })

  it('hides the P(over) note when the line has none', () => {
    expect(nflPropDetail(row(), game(), [], NOW).pOverNote).toBeNull()
  })
})

describe('nflPropDetail status and flags', () => {
  it('defaults injury and depth, and reads trust from the flags', () => {
    expect(nflPropDetail(row(), game(), [], NOW).status).toEqual([
      { label: 'Line shape', value: 'Standard · Full game', note: null },
      { label: 'Injury', value: 'Clear', note: null },
      { label: 'Depth', value: 'Not listed', note: null },
      { label: 'Trust', value: 'Ready', note: null },
    ])
  })

  it('reads injury with practice, depth and a review flag', () => {
    const detail = nflPropDetail(row({
      injuryStatus: 'Questionable', injury: 'Ankle', practiceStatus: 'Limited Participation in Practice',
      depthPosition: 'WR', depthRank: 3, previousDepthPosition: 'WR', previousDepthRank: 3,
      qualityFlags: ['stale_baseline_season', 'historical_baseline', 'opponent_adjusted'],
    }), game(), [], NOW)
    expect(detail.status.map(item => item.value)).toEqual(['Standard · Full game', 'Questionable · Ankle · limited practice', 'WR3', 'Review'])
    expect(detail.flags.map(flag => flag.label)).toEqual(['stale baseline season', 'opponent adjusted'])
    expect(detail.flags[0].tooltip).not.toBe('stale_baseline_season')
  })

  it('carries the sportsbook consensus only when a book priced the line', () => {
    expect(nflPropDetail(row(), game(), [], NOW).sportsbook).toBeNull()
    const priced = nflPropDetail(row({ market: 'anytime_touchdown', bookProbability: 0.3, bookCount: 3, bookIncludesMargin: true, bookFetchedAt: '2026-09-30T10:00:00Z' }), game(), [], NOW)
    expect(priced.sportsbook?.summary).toBeTruthy()
  })
})

describe('nflProjectionHero', () => {
  it('shows the panel projection, its gap and its sample', () => {
    const line = row()
    expect(nflProjectionHero(line, nflPropDetail(line, game(), [], NOW))).toEqual({
      label: 'Projected receiving yards',
      value: '39.1',
      delta: '+25.6 vs 13.5 line',
      reason: null,
      sample: 'based on last 17 games',
      facts: [],
    })
  })

  it('says why there is no number, and drops the delta without a line', () => {
    const none = row({ projection: null, line: null, edge: null })
    expect(nflProjectionHero(none, nflPropDetail(none, game(), [], NOW))).toMatchObject({ value: null, delta: null, reason: 'No projection for this market this week.' })
    const noLine = row({ line: null, edge: null })
    expect(nflProjectionHero(noLine, nflPropDetail(noLine, game(), [], NOW))).toMatchObject({ value: '39.1', delta: null })
  })
})
