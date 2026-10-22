import { describe, expect, it } from 'vitest'
import type { NflGameNotes, NflLineMove, NflNoteInjury, NflSlateGame, NflSlateLine, NflTeamStat, NflTeamStats } from '~/types/nfl'
import { buildNflPropBoard } from '~/utils/nflPropBoard'
import { kickoffWindows, nflSlateRow, nflSlateSummary, slateDigest } from '~/utils/nflSlate'

const EMPTY_SAMPLE = { average: null, values: [] }
const NO_STAT: NflTeamStat = { value: null, rank: null }

function line(lineId: number, overrides: Partial<NflSlateLine> = {}): NflSlateLine {
  return {
    lineId, playerId: lineId, playerName: `Player ${lineId}`, position: 'WR', opponentTeam: 'BUF',
    opponentPositionAverage: null, recentForm: EMPTY_SAMPLE, opponentHistory: EMPTY_SAMPLE, opponentAllowedHistory: EMPTY_SAMPLE,
    market: 'receiving_yards', segment: 'full_game', oddsType: 'standard', projection: 70, line: 60, edge: 10,
    gamesInSample: 8, baselineSeason: 2026, baselineReason: 'current_season', opponentAdjustmentPct: null,
    opponentSampleGames: null, usageAdjustmentPct: null, usageSampleGames: null, provider: 'prizepicks',
    fetchedAt: '2026-10-01T12:00:00Z', projectionModelVersion: 'v', qualityFlags: [], bookProbability: null,
    bookProbabilityDevigged: null, bookCount: null, bookIncludesMargin: null, bookFetchedAt: null, injuryStatus: null,
    practiceStatus: null, injury: null, depthPosition: null, depthRank: null, previousDepthPosition: null,
    previousDepthRank: null, snapShare: null, snapShareGames: null, pOver: null, pUnder: null, overProbabilityVersion: null,
    ...overrides,
  }
}

function game(gameId: number, startUtc: string | null, overrides: Partial<NflSlateGame> = {}): NflSlateGame {
  return {
    gameId, gameDate: '2026-10-04', startUtc, awayTeam: `A${gameId}`, homeTeam: `H${gameId}`, status: 'scheduled', lines: [],
    odds: null, awayContext: null, homeContext: null, model: null,
    weather: { venueType: 'outdoor', forecastFor: null, temperatureF: null, windMph: null, windGustMph: null, precipitationProbability: null, fetchedAt: null },
    ...overrides,
  }
}

function stats(team: string): NflTeamStats {
  return {
    team, games: 0, efficiencyGames: 0, points: NO_STAT, passYards: NO_STAT, rushYards: NO_STAT, plays: NO_STAT,
    passAttempts: NO_STAT, rushAttempts: NO_STAT, passAttemptsAllowed: NO_STAT, rushAttemptsAllowed: NO_STAT,
    epaPerPlay: NO_STAT, successRate: NO_STAT, pointsAllowed: NO_STAT, passYardsAllowed: NO_STAT,
    rushYardsAllowed: NO_STAT, playsAllowed: NO_STAT, epaPerPlayAllowed: NO_STAT, successRateAllowed: NO_STAT,
  }
}

function notes(gameId: number, overrides: Partial<NflGameNotes> = {}): NflGameNotes {
  return {
    gameId, awayTeam: `A${gameId}`, homeTeam: `H${gameId}`, injuries: [], depthChanges: [], lineMovement: [],
    awayForm: { team: `A${gameId}`, restDays: null, shortWeek: false, recent: [] },
    homeForm: { team: `H${gameId}`, restDays: null, shortWeek: false, recent: [] },
    awayStats: stats(`A${gameId}`), homeStats: stats(`H${gameId}`), awayScore: null, homeScore: null, awayQbChange: null, homeQbChange: null, bestLine: null,
    ...overrides,
  }
}

function injury(injuryStatus: string | null, practiceStatus: string | null = null): NflNoteInjury {
  return { playerId: 1, playerName: 'P', team: 'A1', position: 'WR', injuryStatus, practiceStatus, injury: null }
}

function move(currentFetchedAt: string): NflLineMove {
  return { market: 'spread', book: 'draftkings', openLine: -3, openFetchedAt: '2026-09-29T14:00:00Z', currentLine: -3.5, currentFetchedAt, move: -0.5 }
}

// 2026 week 5 in Central daylight time (UTC-5): Thu Oct 1 to Mon Oct 5.
const WEEK = [
  game(1, '2026-10-05T23:15:00Z'), // MNF 6:15 PM
  game(2, '2026-10-04T17:00:00Z', { awayTeam: 'NYJ' }), // Sun 12:00 PM
  game(3, '2026-10-02T00:15:00Z'), // Thu 7:15 PM
  game(4, '2026-10-04T13:30:00Z'), // Sun 8:30 AM, London
  game(5, null),
  game(6, '2026-10-04T20:25:00Z'), // Sun 3:25 PM
  game(7, '2026-10-05T00:20:00Z'), // SNF 7:20 PM
  game(8, '2026-10-04T17:00:00Z', { awayTeam: 'BUF' }), // Sun 12:00 PM
  game(9, '2026-10-06T00:15:00Z'), // MNF 7:15 PM, doubleheader
]

describe('kickoffWindows', () => {
  it('groups by Central weekday and kickoff, ordered by the earliest game', () => {
    const windows = kickoffWindows(WEEK)

    expect(windows.map(window => window.title)).toEqual([
      'Thursday · 7:15 PM CT',
      'Sunday · 8:30 AM CT',
      'Sunday · 12:00 PM CT',
      'Sunday · 3:25 PM CT',
      'Prime time',
      'Kickoff time not set',
    ])
  })

  it('merges SNF and a Monday doubleheader into one prime-time window', () => {
    const prime = kickoffWindows(WEEK).find(window => window.title === 'Prime time')

    expect(prime?.games.map(item => item.gameId)).toEqual([7, 1, 9])
    expect(prime?.subtitle).toBe('SNF and MNF · 3 games')
  })

  it('names only the nights a prime-time window holds', () => {
    expect(kickoffWindows([game(1, '2026-10-05T23:15:00Z')])[0].subtitle).toBe('MNF · 1 game')
  })

  it('orders games in a window by kickoff, then away team', () => {
    const noon = kickoffWindows(WEEK).find(window => window.title === 'Sunday · 12:00 PM CT')

    expect(noon?.games.map(item => item.awayTeam)).toEqual(['BUF', 'NYJ'])
    expect(noon?.subtitle).toBe('2 games')
  })

  it('treats an unparseable kickoff as not set', () => {
    expect(kickoffWindows([game(1, 'not a date')])[0].title).toBe('Kickoff time not set')
  })

  it('returns no windows for an empty week', () => {
    expect(kickoffWindows([])).toEqual([])
  })
})

describe('nflSlateSummary', () => {
  const games = [
    game(1, '2026-10-04T17:00:00Z', {
      status: 'completed',
      // An alternate of the same player, market and segment counts once.
      lines: [line(11), line(12, { playerId: 11, oddsType: 'goblin', line: 50 }), line(13)],
    }),
    game(2, '2026-10-04T20:25:00Z', { lines: [line(21)] }),
  ]

  it('leaves the notes-backed stats null while notes are unavailable', () => {
    expect(nflSlateSummary(games, undefined)).toEqual({ games: 2, propLines: 3, finals: 1, outOrDoubtful: null, oddsUpdated: null })
  })

  it('counts Out and Doubtful report statuses only, and reads the latest odds fetch in CT', () => {
    const summary = nflSlateSummary(games, [
      notes(1, {
        injuries: [injury('Out'), injury('Doubtful'), injury('Questionable'), injury(null, 'Did Not Participate')],
        lineMovement: [move('2026-09-29T19:10:00Z')],
      }),
      notes(2, { lineMovement: [move('2026-09-30T14:05:00Z')] }),
    ])

    expect(summary.outOrDoubtful).toBe(2)
    expect(summary.oddsUpdated).toBe('Wed 9:05 AM CT')
  })

  it('has no odds time when notes hold no movement', () => {
    expect(nflSlateSummary(games, [notes(1)]).oddsUpdated).toBeNull()
  })
})

describe('slateDigest', () => {
  const NOW = new Date('2026-10-04T12:00:00Z')
  const rushing = { market: 'rushing_yards', line: 50 }
  const week = [
    game(1, '2026-10-04T17:00:00Z', {
      lines: [
        line(11, { edge: 10 }), // 17%
        line(12, { edge: 20, qualityFlags: ['injury_out'] }), // 33%, but ruled out
        line(13, { edge: -15 }), // 25%, same player as line 15
        line(15, { ...rushing, playerId: 13, playerName: 'Player 13', edge: 30 }), // 60%
        line(16, { edge: 50, oddsType: 'goblin', line: 45 }), // never rateable
        line(17, { market: 'anytime_touchdown', line: 0.5, edge: 0.4 }), // never rateable until 25c
      ],
    }),
    game(2, '2026-10-04T20:25:00Z', { lines: [line(21, { edge: 40, projection: 100 }), line(22, { ...rushing, edge: -20, projection: 30 })] }), // 67%, 40%
    game(3, '2026-10-04T11:00:00Z', { lines: [line(31, { edge: 59 })] }), // already kicked off
  ]

  it('ranks the week by board tier then edge share, one per player, without started games or unrateable lines', () => {
    const digest = slateDigest(buildNflPropBoard(week, 'all', NOW))

    expect(digest.map(item => item.lineId)).toEqual([21, 15, 22, 11])
    expect(slateDigest(buildNflPropBoard(week, 'all', NOW), 10).map(item => item.lineId)).toEqual([21, 15, 22, 11, 12])
  })

  it('carries display strings for a box', () => {
    const [first, second] = slateDigest(buildNflPropBoard(week, 'all', NOW))

    expect(first).toEqual({ lineId: 21, gameId: 2, playerName: 'Player 21', market: 'Receiving yards', matchup: 'A2 @ H2', line: '60.0', model: '100.0', gap: '+66.7%' })
    expect([second.matchup, second.market, second.gap]).toEqual(['A1 @ H1', 'Rushing yards', '+60.0%'])
  })

  it('is empty when nothing upcoming is rateable', () => {
    expect(slateDigest(buildNflPropBoard(week, 'all', new Date('2026-10-05T12:00:00Z')))).toEqual([])
    expect(slateDigest([])).toEqual([])
  })
})

describe('nflSlateRow', () => {
  const BEFORE = new Date('2026-10-04T12:00:00Z')
  const DURING = new Date('2026-10-04T18:00:00Z')
  const ODDS = { book: 'draftkings', homeMoneyline: -142, awayMoneyline: 120, homeSpread: -2.5, total: 48.5 }
  const MODEL = { modelVersion: 'nfl-elo-v1', homeElo: 1550, awayElo: 1500, homeWinProbability: 0.57, homeSpread: -1, total: 46.9, marketHomeWinProbability: 0.58 }
  const DOME = { venueType: 'dome' as const, forecastFor: null, temperatureF: null, windMph: null, windGustMph: null, precipitationProbability: null, fetchedAt: null }

  function lineMove(market: 'spread' | 'total', openLine: number, currentLine: number, change: number | null): NflLineMove {
    return { market, book: 'draftkings', openLine, openFetchedAt: '2026-09-29T14:00:00Z', currentLine, currentFetchedAt: '2026-10-03T14:00:00Z', move: change }
  }

  function final(homeLine: number, totalLine: number, awayScore: number, homeScore: number) {
    const played = game(1, '2026-10-04T17:00:00Z', { status: 'completed', odds: ODDS })
    const gameNotes = notes(1, { awayScore, homeScore, lineMovement: [lineMove('spread', homeLine, homeLine, 0), lineMove('total', totalLine, totalLine, 0)] })
    return nflSlateRow(played, gameNotes, DURING)
  }

  it.each([
    [-3.5, 17, 24, 'H1 covered'],
    [-3.5, 17, 20, 'A1 covered'],
    [-3, 17, 20, 'push'],
    [2.5, 21, 17, 'A1 covered'],
    [2.5, 19, 17, 'H1 covered'],
  ])('grades a home line of %d on a %d-%d final as %s', (homeLine, awayScore, homeScore, result) => {
    expect(final(homeLine, 44.5, awayScore, homeScore).spread.detail).toBe(result)
  })

  it.each([
    [44.5, 17, 24, 'under by 3.5'],
    [37.5, 17, 24, 'over by 3.5'],
    [41, 17, 24, 'push'],
  ])('grades a total of %d against %d-%d as %s', (totalLine, awayScore, homeScore, result) => {
    expect(final(-3, totalLine, awayScore, homeScore).total.detail).toBe(result)
  })

  it.each([
    [-142, 120, 'H1 -142', 'A1 +120'],
    [130, -150, 'A1 -150', 'H1 +130'],
    [-110, -110, 'H1 -110', 'A1 -110'],
  ])('names the moneyline favorite for home %d, away %d', (homeMoneyline, awayMoneyline, value, detail) => {
    expect(nflSlateRow(game(1, null, { odds: { ...ODDS, homeMoneyline, awayMoneyline } }), undefined, BEFORE).moneyline).toEqual({ value, detail })
  })

  it('counts injuries by report status only, and tags each team whose QB changed, away first', () => {
    const change = (team: string) => ({
      team, usualStarter: 'Starter', reasons: ['backup_started' as const], injuryStatus: null, injuryWeek: null,
      lastGameQb: 'Backup', lastGameWeek: 4, previousQb1: null,
    })
    const row = nflSlateRow(game(1, null), notes(1, {
      injuries: [injury('Out'), injury('Out'), injury('Doubtful'), injury('Questionable'), injury(null, 'Limited Participation')],
      awayQbChange: change('A1'), homeQbChange: change('H1'),
    }), BEFORE)

    expect(row.injuries).toEqual({ out: 2, doubtful: 1, questionable: 1 })
    expect(row.qbChange).toEqual(['A1', 'H1'])
  })

  it('builds an upcoming row from the market, its moves, the muted model and the prop count', () => {
    const upcoming = game(1, '2026-10-04T17:00:00Z', {
      odds: ODDS, model: MODEL, weather: DOME, lines: [line(11), line(12, { playerId: 11, oddsType: 'goblin', line: 45 }), line(13, { market: 'rushing_yards' })],
      awayContext: { games: 3, wins: 2, losses: 1, pointsForPerGame: 24, pointsAllowedPerGame: 20 },
    })
    const gameNotes = notes(1, {
      lineMovement: [lineMove('spread', -1.5, -2.5, -1), lineMove('total', 48.5, 48.5, 0)],
      injuries: [injury('Out'), injury('Questionable')],
      awayForm: { team: 'A1', restDays: 4, shortWeek: true, recent: [] },
    })

    const row = nflSlateRow(upcoming, gameNotes, BEFORE)

    expect([row.state, row.kickoff, row.away.record, row.home.record]).toEqual(['upcoming', 'Sun 12:00 PM', '2-1', 'No games yet'])
    expect([row.spread, row.total, row.moneyline]).toEqual([
      { value: 'H1 -2.5', detail: 'opened H1 -1.5' }, { value: '48.5', detail: 'no move' }, { value: 'H1 -142', detail: 'A1 +120' },
    ])
    expect(row.model).toEqual({ spread: 'H1 -1.0', total: '46.9' })
    expect(row.props).toBe(2)
    expect([row.conditions, row.injuries, row.shortWeek, row.qbChange]).toEqual(['Indoor', { out: 1, doubtful: 0, questionable: 1 }, ['A1'], []])
  })

  it('marks a kicked-off game live and keeps its market', () => {
    const row = nflSlateRow(game(1, '2026-10-04T17:00:00Z', { odds: ODDS }), undefined, DURING)

    expect([row.state, row.kickoff, row.spread.value]).toEqual(['live', 'Sun 12:00 PM', 'H1 -2.5'])
  })

  it('grades a final against its close and drops the pre-game tags', () => {
    const played = game(1, '2026-10-04T17:00:00Z', { status: 'completed', odds: ODDS, lines: [line(11)] })
    const gameNotes = notes(1, {
      awayScore: 17, homeScore: 24, injuries: [injury('Out')],
      lineMovement: [lineMove('spread', -3.5, -3.5, 0), lineMove('total', 44.5, 44.5, 0)],
    })

    const row = nflSlateRow(played, gameNotes, DURING)

    expect([row.state, row.kickoff]).toEqual(['final', 'Final'])
    expect([row.away.score, row.away.lost, row.home.score, row.home.lost]).toEqual([17, true, 24, false])
    expect([row.spread, row.total, row.moneyline]).toEqual([
      { value: 'H1 -3.5', detail: 'H1 covered' }, { value: '44.5', detail: 'under by 3.5' }, { value: '--', detail: null },
    ])
    expect([row.injuries, row.shortWeek, row.props]).toEqual([null, [], 1])
  })

  it('leaves a final without a stored score ungraded', () => {
    const row = nflSlateRow(game(1, '2026-10-04T17:00:00Z', { status: 'completed', odds: ODDS }), notes(1), DURING)

    expect([row.kickoff, row.away.score, row.home.score, row.spread.value, row.total.value]).toEqual(['Final', null, null, '--', '--'])
  })

  it('degrades without a kickoff, odds, model or notes', () => {
    const row = nflSlateRow(game(1, null), undefined, BEFORE)

    expect([row.kickoff, row.spread.value, row.total.value, row.moneyline.value, row.model, row.injuries, row.props]).toEqual(['--', '--', '--', '--', null, null, 0])
  })
})
