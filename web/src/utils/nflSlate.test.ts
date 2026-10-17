import { describe, expect, it, vi } from 'vitest'
import type { NflGameNotes, NflLineMove, NflNoteInjury, NflSlateGame, NflSlateLine, NflTeamStat, NflTeamStats } from '~/types/nfl'
import { buildNflPropBoard } from '~/utils/nflPropBoard'
import { kickoffWindows, nflSlateCard, nflSlateSummary, slateBoards, topGameProps } from '~/utils/nflSlate'

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

describe('topGameProps', () => {
  const NOW = new Date('2026-10-04T12:00:00Z')
  const rushing = { market: 'rushing_yards', line: 50 }
  const week = [
    game(1, '2026-10-04T17:00:00Z', {
      lines: [
        line(11, { edge: 10 }), // 10 / 60 = 17%
        line(12, { edge: 20, qualityFlags: ['injury_out'] }), // 33%, but ruled out
        line(13, { edge: -15 }), // 25%, same player as line 15
        line(14, { ...rushing, edge: 20 }), // 40%
        line(15, { ...rushing, playerId: 13, playerName: 'Player 13', edge: 30 }), // 60%
        line(16, { edge: 50, oddsType: 'goblin', line: 45 }), // an alternate payout is never rateable
        line(17, { edge: 50, segment: 'first_half' }), // nor is a partial game
      ],
    }),
    game(2, '2026-10-04T20:25:00Z', { lines: [line(21, { edge: 40 })] }),
  ]

  it('ranks across markets by edge share, sinks an out player, and keeps one row per player', () => {
    const board = buildNflPropBoard(week, 'all', NOW)

    expect(topGameProps(board, 1).map(item => item.row.lineId)).toEqual([15, 14, 11])
    expect(topGameProps(board, 1, 10).map(item => item.row.lineId)).toEqual([15, 14, 11, 12])
    expect(topGameProps(board, 1)[0].edgeShare).toBeCloseTo(0.6)
  })

  it('reads a started game as of kickoff, so its props survive the board dropping it', () => {
    const afterKickoff = new Date('2026-10-04T18:00:00Z')

    expect(buildNflPropBoard(week, 'all', afterKickoff).flatMap(category => category.rateable).some(row => row.gameId === 1)).toBe(false)
    expect(topGameProps(slateBoards(week, afterKickoff).get(1) ?? [], 1).map(item => item.row.lineId)).toEqual([15, 14, 11])
  })

  it('returns nothing for a game without rateable lines', () => {
    expect(topGameProps(buildNflPropBoard(week, 'all', NOW), 3)).toEqual([])
  })
})

describe('slateBoards', () => {
  it('builds the board once for a week of upcoming games', () => {
    const build = vi.fn(buildNflPropBoard)
    const week = [game(1, '2026-10-04T17:00:00Z'), game(2, '2026-10-04T20:25:00Z'), game(3, null)]

    const boards = slateBoards(week, new Date('2026-10-04T12:00:00Z'), build)

    expect(build).toHaveBeenCalledTimes(1)
    expect([...boards.keys()]).toEqual([1, 2, 3])
  })

  it('adds one build per started game, each as of just before its kickoff', () => {
    const build = vi.fn(buildNflPropBoard)
    const week = [game(1, '2026-10-04T17:00:00Z'), game(2, '2026-10-04T20:25:00Z'), game(3, '2026-10-05T00:20:00Z')]

    slateBoards(week, new Date('2026-10-04T21:00:00Z'), build)

    expect(build.mock.calls.map(call => call[2]?.toISOString())).toEqual([
      '2026-10-04T16:59:59.999Z',
      '2026-10-04T20:24:59.999Z',
      '2026-10-04T21:00:00.000Z',
    ])
  })
})

describe('nflSlateCard', () => {
  const BEFORE = new Date('2026-10-04T12:00:00Z')
  const DURING = new Date('2026-10-04T18:00:00Z')
  const ODDS = { book: 'draftkings', homeMoneyline: -142, awayMoneyline: 120, homeSpread: -2.5, total: 48.5 }
  const MODEL = { modelVersion: 'nfl-elo-v1', homeElo: 1550, awayElo: 1500, homeWinProbability: 0.57, homeSpread: -1, total: 46.9, marketHomeWinProbability: 0.58 }

  function lineMove(market: 'spread' | 'total', openLine: number, currentLine: number, change: number | null): NflLineMove {
    return { market, book: 'draftkings', openLine, openFetchedAt: '2026-09-29T14:00:00Z', currentLine, currentFetchedAt: '2026-10-03T14:00:00Z', move: change }
  }

  function final(homeLine: number, totalLine: number, awayScore: number, homeScore: number) {
    const played = game(1, '2026-10-04T17:00:00Z', { status: 'completed', odds: ODDS })
    const gameNotes = notes(1, { awayScore, homeScore, lineMovement: [lineMove('spread', homeLine, homeLine, 0), lineMove('total', totalLine, totalLine, 0)] })
    return nflSlateCard(played, gameNotes, [], DURING)
  }

  it.each([
    [-3.5, 17, 24, 'H1 covered'],
    [-3.5, 17, 20, 'A1 covered'],
    [-3, 17, 20, 'push'],
    [2.5, 21, 17, 'A1 covered'],
    [2.5, 19, 17, 'H1 covered'],
  ])('grades a home line of %d on a %d-%d final as %s', (homeLine, awayScore, homeScore, result) => {
    expect(final(homeLine, 44.5, awayScore, homeScore).final?.[0]?.detail).toBe(result)
  })

  it.each([
    [44.5, 17, 24, 'under by 3.5'],
    [37.5, 17, 24, 'over by 3.5'],
    [41, 17, 24, 'push'],
  ])('grades a total of %d against %d-%d as %s', (totalLine, awayScore, homeScore, result) => {
    expect(final(-3, totalLine, awayScore, homeScore).final?.[1]?.detail).toBe(result)
  })

  it('shows a final with its score, the loser marked, and no props or model teaser', () => {
    const card = final(-3.5, 44.5, 17, 24)

    expect(card.state).toBe('final')
    expect([card.away.score, card.away.lost, card.home.score, card.home.lost]).toEqual([17, true, 24, false])
    expect(card.final?.map(cell => [cell.label, cell.value])).toEqual([['Close spread', 'H1 -3.5'], ['Close total', '44.5'], ['Props', '0']])
    expect(card.topProps).toEqual([])
  })

  it('leaves a final without a stored score ungraded', () => {
    const card = nflSlateCard(game(1, '2026-10-04T17:00:00Z', { status: 'completed' }), notes(1), [], DURING)

    expect(card.state).toBe('final')
    expect(card.final).toBeNull()
    expect([card.away.score, card.home.score]).toEqual([null, null])
  })

  it('counts injuries by report status only', () => {
    const card = nflSlateCard(game(1, null), notes(1, {
      injuries: [injury('Out'), injury('Out'), injury('Doubtful'), injury('Questionable'), injury(null, 'Limited Participation')],
    }), [], BEFORE)

    expect(card.injuries).toEqual({ out: 2, doubtful: 1, questionable: 1 })
  })

  it.each([
    [-142, 120, 'H1 -142', 'A1 +120'],
    [130, -150, 'A1 -150', 'H1 +130'],
    [-110, -110, 'H1 -110', 'A1 -110'],
  ])('names the moneyline favorite for home %d, away %d', (homeMoneyline, awayMoneyline, value, detail) => {
    const card = nflSlateCard(game(1, null, { odds: { ...ODDS, homeMoneyline, awayMoneyline } }), undefined, [], BEFORE)

    expect(card.market?.[2]).toEqual({ label: 'Moneyline', value, detail })
  })

  it('builds an upcoming card from the market, the muted model, movement, rest and the top props', () => {
    const upcoming = game(1, '2026-10-04T17:00:00Z', {
      odds: ODDS, model: MODEL, lines: [line(11, { edge: 12 }), line(12, { edge: 6, oddsType: 'goblin' })],
      awayContext: { games: 3, wins: 2, losses: 1, pointsForPerGame: 24, pointsAllowedPerGame: 20 },
    })
    const gameNotes = notes(1, {
      lineMovement: [lineMove('spread', -1.5, -2.5, -1), lineMove('total', 48.5, 48.5, 0)],
      awayForm: { team: 'A1', restDays: 4, shortWeek: true, recent: [] },
      homeForm: { team: 'H1', restDays: 7, shortWeek: false, recent: [] },
    })

    const card = nflSlateCard(upcoming, gameNotes, buildNflPropBoard([upcoming], 'all', BEFORE), BEFORE)

    expect(card.state).toBe('upcoming')
    expect([card.away.record, card.away.rest, card.home.rest]).toEqual(['2-1', 'rest 4', 'rest 7'])
    expect(card.shortWeek).toEqual(['A1'])
    expect(card.qbChange).toEqual([])
    expect(card.winBar).toEqual({ away: 44, home: 56 })
    expect(card.market?.map(cell => [cell.value, cell.detail])).toEqual([['H1 -2.5', 'opened H1 -1.5'], ['48.5', 'no move'], ['H1 -142', 'A1 +120']])
    expect(card.model).toEqual({ spread: 'H1 -1.0', total: '46.9', winProbability: 'H1 57.0%' })
    expect(card.topProps).toEqual([{ lineId: 11, playerName: 'Player 11', market: 'Receiving yards', line: '60.0', edge: '+20.0%' }])
    expect([card.rateableCount, card.otherCount]).toEqual([1, 1])
  })

  it('marks a kicked-off game live and keeps its props as of kickoff', () => {
    const started = game(1, '2026-10-04T17:00:00Z', { lines: [line(11)] })

    const card = nflSlateCard(started, undefined, slateBoards([started], DURING).get(1) ?? [], DURING)

    expect(card.state).toBe('live')
    expect(card.topProps.map(prop => prop.lineId)).toEqual([11])
  })

  it('shows the best spread per side and its short book on an upcoming card only', () => {
    const side = (which: 'home' | 'away', line: number, book: string) => ({
      side: which, line, odds: -110, book, provider: 'odds_api_io', fetchedAt: '2026-10-04T15:00:00Z', evPct: null, pointsVsFair: null,
    })
    const bestLine = { maxAgeHours: 36, markets: [{ market: 'spread' as const, fair: null, sides: [side('home', -8.5, 'draftkings'), side('away', -9.5, 'bet365')] }] }
    const gameNotes = notes(1, { bestLine })

    expect(nflSlateCard(game(1, '2026-10-04T17:00:00Z'), gameNotes, [], BEFORE).bestSpread).toBe('Best H1 -8.5 DK · A1 +9.5 B365')
    expect(nflSlateCard(game(1, '2026-10-04T17:00:00Z'), gameNotes, [], DURING).bestSpread).toBeNull()
    expect(nflSlateCard(game(1, '2026-10-04T17:00:00Z'), notes(1), [], BEFORE).bestSpread).toBeNull()
  })

  it('tags each team whose QB changed, away first', () => {
    const change = (team: string) => ({
      team, usualStarter: 'Starter', reasons: ['backup_started' as const], injuryStatus: null, injuryWeek: null,
      lastGameQb: 'Backup', lastGameWeek: 4, previousQb1: null,
    })
    const gameNotes = notes(1, { awayQbChange: change('A1'), homeQbChange: change('H1') })

    const card = nflSlateCard(game(1, '2026-10-04T17:00:00Z'), gameNotes, [], BEFORE)

    expect(card.qbChange).toEqual(['A1', 'H1'])
  })

  it('degrades without odds, model or notes', () => {
    const card = nflSlateCard(game(1, null), undefined, [], BEFORE)
    expect(card.qbChange).toEqual([])

    expect([card.market, card.winBar, card.model, card.injuries, card.final]).toEqual([null, null, null, null, null])
    expect([card.away.record, card.away.rest, card.kickoff, card.shortWeek]).toEqual(['No games yet', null, 'Kickoff time not set', []])
  })
})
