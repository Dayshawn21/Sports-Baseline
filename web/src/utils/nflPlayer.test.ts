import { describe, expect, it } from 'vitest'
import type { NflPlayerUsage, NflSlateGame, NflSlateLine } from '~/types/nfl'
import { buildNflPropBoard } from '~/utils/nflPropBoard'
import { isNflSpecialist, nflPlayerMarketLink, SPECIALIST_COLUMNS, playerInitials, playerWeekLines, usageBars } from '~/utils/nflPlayer'

const EMPTY_SAMPLE = { average: null, values: [] }
const NOW = new Date('2026-10-04T12:00:00Z')

function line(lineId: number, overrides: Partial<NflSlateLine> = {}): NflSlateLine {
  return {
    lineId, playerId: lineId, playerName: `Player ${lineId}`, position: 'RB', opponentTeam: 'MIA',
    opponentPositionAverage: null, recentForm: EMPTY_SAMPLE, opponentHistory: EMPTY_SAMPLE, opponentAllowedHistory: EMPTY_SAMPLE,
    market: 'rushing_yards', segment: 'full_game', oddsType: 'standard', projection: 70, line: 60, edge: 10,
    gamesInSample: 8, baselineSeason: 2026, baselineReason: 'current_season', opponentAdjustmentPct: null,
    opponentSampleGames: null, usageAdjustmentPct: null, usageSampleGames: null, provider: 'prizepicks',
    fetchedAt: '2026-10-01T12:00:00Z', projectionModelVersion: 'v', qualityFlags: [], bookProbability: null,
    bookProbabilityDevigged: null, bookCount: null, bookIncludesMargin: null, bookFetchedAt: null, injuryStatus: null,
    practiceStatus: null, injury: null, depthPosition: null, depthRank: null, previousDepthPosition: null,
    previousDepthRank: null, snapShare: null, snapShareGames: null, pOver: null, pUnder: null, overProbabilityVersion: null,
    ...overrides,
  }
}

function game(gameId: number, lines: NflSlateLine[]): NflSlateGame {
  return {
    gameId, gameDate: '2026-10-04', startUtc: '2026-10-04T17:00:00Z', awayTeam: 'BUF', homeTeam: 'MIA', status: 'scheduled', lines,
    odds: null, awayContext: null, homeContext: null, model: null,
    weather: { venueType: 'outdoor', forecastFor: null, temperatureF: null, windMph: null, windGustMph: null, precipitationProbability: null, fetchedAt: null },
  }
}

const COOK = 7
const WEEK = [
  game(1, [
    line(11, { playerId: COOK, edge: 9 }),
    line(12, { playerId: COOK, oddsType: 'goblin', line: 50, edge: 20 }),
    line(13, { playerId: COOK, market: 'anytime_touchdown', line: 0.5, projection: 0.38, edge: null, bookProbabilityDevigged: 0.44 }),
    line(14, { playerId: COOK, segment: 'first_half', line: 30, edge: 4 }),
    line(15, { edge: 30 }),
  ]),
  game(2, [line(21, { edge: 5 })]),
]

describe('playerWeekLines', () => {
  it('keeps the player full-game primary rows with board ranks and edge share', () => {
    const week = playerWeekLines(WEEK, COOK, NOW)
    const board = buildNflPropBoard(WEEK, 'all', NOW)
    const rushing = board.find(category => category.market === 'rushing_yards')

    expect(week?.game.gameId).toBe(1)
    expect(week?.lines.map(item => item.row.lineId)).toEqual([11, 13])
    expect(week?.lines[0]?.rank).toBe((rushing?.rateable.findIndex(row => row.lineId === 11) ?? -1) + 1)
    expect(week?.lines[0]?.edgeShare).toBeCloseTo(9 / 60)
    expect(week?.lines[0]?.alternates.map(alternate => alternate.lineId)).toEqual([12])
  })

  it('keeps anytime TD without a rank or edge', () => {
    const td = playerWeekLines(WEEK, COOK, NOW)?.lines.find(item => item.row.market === 'anytime_touchdown')

    expect([td?.rank, td?.edgeShare, td?.row.bookProbabilityDevigged]).toEqual([null, null, 0.44])
  })

  it('is null for a player without a line this week', () => {
    expect(playerWeekLines(WEEK, 999, NOW)).toBeNull()
  })

  it('is null when the player has only partial-game lines', () => {
    expect(playerWeekLines([game(1, [line(14, { playerId: COOK, segment: 'first_half' })])], COOK, NOW)).toBeNull()
  })
})

function usage(week: number, overrides: Partial<NflPlayerUsage> = {}): NflPlayerUsage {
  return { season: 2026, week, previousSeason: false, passingAttempts: 0, rushingAttempts: 10, targets: 2, receptions: 1, snapPct: 0.5, ...overrides }
}

describe('usageBars', () => {
  it('scales counts to the row maximum and averages per game', () => {
    const row = usageBars([usage(1, { rushingAttempts: 10, previousSeason: true, season: 2025 }), usage(2, { rushingAttempts: 20 })], 'rushing_attempts')

    expect(row.bars.map(bar => [bar.week, bar.heightPct, bar.previousSeason])).toEqual([[1, 50, true], [2, 100, false]])
    expect([row.label, row.average]).toEqual(['Carries', '15.0 / g'])
  })

  it('scales snap share to 100% and skips missing snaps', () => {
    const row = usageBars([usage(1, { snapPct: 0.64 }), usage(2, { snapPct: null })], 'snap_pct')

    expect(row.bars.map(bar => bar.heightPct)).toEqual([64, 0])
    expect(row.average).toBe('64%')
  })

  it('draws flat bars when every game is zero or missing', () => {
    const row = usageBars([usage(1, { targets: 0 }), usage(2, { targets: null })], 'targets')

    expect(row.bars.map(bar => bar.heightPct)).toEqual([0, 0])
    expect(row.average).toBe('0.0 / g')
    expect(usageBars([], 'targets').average).toBe('--')
  })
})

describe('playerInitials', () => {
  it.each([
    ['James Cook', 'JC'],
    ['Oronde Gadsden II', 'OG'],
    ['Michael Penix Jr.', 'MP'],
    ["Ja'Marr Chase", 'JC'],
    ['Pelé', 'P'],
    ['', '--'],
  ])('%s is %s', (name, initials) => {
    expect(playerInitials(name)).toBe(initials)
  })
})


describe('specialist player pages', () => {
  it('restricts specialist layout to kickers and punters', () => {
    expect(['K', 'P', 'QB', 'RB', 'WR', 'TE', null].map(isNflSpecialist)).toEqual([true, true, false, false, false, false, false])
  })
  it('selects only the correct specialist fields and market identity', () => {
    expect(SPECIALIST_COLUMNS.K.map(column => [column.field, column.market])).toEqual([
      ['fgMade', 'field_goals_made'], ['patMade', null], ['kickingPoints', 'kicking_points'],
    ])
    expect(SPECIALIST_COLUMNS.P).toEqual([{ field: 'punts', label: 'Punts', market: 'punts' }])
  })
  it('carries the encoded market to the player game log', () => {
    expect(nflPlayerMarketLink(40440, 'kicking_points')).toBe('/nfl/player/40440?market=kicking_points#game-log')
    expect(nflPlayerMarketLink(1, 'a&b')).toContain('market=a%26b')
  })
})
