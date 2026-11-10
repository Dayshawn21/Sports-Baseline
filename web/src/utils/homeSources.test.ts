import { describe, expect, it } from 'vitest'
import type { NflSlateGame, NflSlateResponse } from '~/types/nfl'
import type { MatchPrediction, PropLine } from '~/types/tennis'
import type { NhlSlateGame } from '~/types/nhl'
import { GAPS_PER_SPORT, HERO_NEXT_LIMIT, SCHEDULE_LIMIT, isZeroGap, reconciledStart, tennisGapRows, isPricedMatch, nbaSource, nflSource, nhlSource, tennisSource } from '~/utils/homeSources'
import type { NbaSlateDigestItem } from '~/utils/nbaSlate'

const HOUR = 60 * 60 * 1000
// Tue 2026-11-03 17:00 UTC = 11:00 CT.
const NOW = Date.UTC(2026, 10, 3, 17, 0)
const at = (hours: number) => new Date(NOW + hours * HOUR).toISOString()

function nhlGame(gameId: number, hours: number | null, status = 'scheduled'): NhlSlateGame {
  return {
    gameId, season: 2026, week: null, gameType: 'REG', gameDate: '2026-11-03', startUtc: hours === null ? null : at(hours), status,
    awayTeam: `A${gameId}`, homeTeam: `H${gameId}`, awayTeamName: '', homeTeamName: '', awayScore: null, homeScore: null,
    endPeriod: null, awayRecord: { wins: 0, losses: 0, otLosses: 0 }, homeRecord: { wins: 0, losses: 0, otLosses: 0 }, propLineCount: 10, moneyline: null, spread: null, total: null,
  } as NhlSlateGame
}

function match(matchId: number, hours: number | null, odds: [number | null, number | null] = [-110, 100]): MatchPrediction {
  return {
    matchId, startUtc: hours === null ? null : at(hours), p1Name: `P${matchId}`, p2Name: `Q${matchId}`, tour: 'ATP', surface: null,
    tournament: null, round: null, p1WinProb: null, p2WinProb: null, p1EloProb: null, p1MlProb: null, p1MarketProb: null,
    ensembleWeights: {}, qualityFlags: [], p1OddsAmerican: odds[0], p2OddsAmerican: odds[1], h2hP1Wins: 0, h2hP2Wins: 0,
  }
}

describe('nhlSource', () => {
  it('counts the slate, keeps unfinished starts and lists the next games in order', () => {
    const games = [nhlGame(1, 9), nhlGame(2, 3), nhlGame(3, -4, 'completed'), nhlGame(4, 5), nhlGame(5, 7), nhlGame(6, null)]
    const source = nhlSource(games, NOW)
    expect(source.gameCount).toBe(6)
    expect(source.propLines).toBe(60)
    expect(source.startsMs).toHaveLength(4)
    expect(source.nextGames.map(game => game.title)).toEqual(['A2 @ H2', 'A4 @ H4', 'A5 @ H5'])
    expect(source.nextGames).toHaveLength(HERO_NEXT_LIMIT)
    expect(source.nextGames[0].when).toBe('2:00 PM')
    expect(source.gaps).toEqual([])
    expect(source.period).toBeNull()
  })

  it('keeps a longer schedule for the gaps tab, soonest first and capped at ten', () => {
    const games = Array.from({ length: 12 }, (_, n) => nhlGame(n + 1, 12 - n))
    games.push(nhlGame(20, -2), nhlGame(21, 3, 'completed'))
    const { schedule, nextGames } = nhlSource(games, NOW)
    expect(schedule).toHaveLength(SCHEDULE_LIMIT)
    expect(schedule[0]).toEqual({ key: '12', title: 'A12 @ H12', when: '12:00 PM', path: '/nhl/game/12' })
    expect(schedule.map(game => game.key)).not.toContain('20')
    expect(schedule.map(game => game.key)).not.toContain('21')
    expect(nextGames.map(game => game.key)).toEqual(schedule.slice(0, HERO_NEXT_LIMIT).map(game => game.key))
  })

  it('is empty for no games', () => {
    expect(nhlSource([], NOW)).toMatchObject({ gameCount: 0, startsMs: [], nextGames: [], schedule: [] })
  })

  it('leaves a started game out of the next list but keeps it in the count', () => {
    const source = nhlSource([nhlGame(1, -1), nhlGame(2, 2)], NOW)
    expect(source.gameCount).toBe(2)
    expect(source.nextGames.map(game => game.key)).toEqual(['2'])
  })
})

describe('nbaSource', () => {
  it('links each next game to its game page', () => {
    const game = { gameId: 42, startUtc: at(3), awayTeam: 'NO', homeTeam: 'GS', status: 'scheduled', lines: [], moneyline: null, spread: null, total: null, propLineCount: 0 } as unknown as Parameters<typeof nbaSource>[0][number]
    expect(nbaSource([game], [], '2026-11-03', NOW).nextGames).toEqual([{ key: '42', title: 'NO @ GS', when: '2:00 PM', path: '/nba/game/42' }])
  })

  it('drops a zero gap before the cut and keeps the rest in digest order', () => {
    const item = (n: number, gap: string): NbaSlateDigestItem => ({
      key: `k${n}`, gameId: n, playerId: n, playerName: `Player ${n}`, marketKey: 'points', market: 'Points', matchup: 'A @ B',
      when: 'x', line: '20.5', model: '20.5', gap, gapScaled: null, gapShare: '0%',
    })
    const digest = [item(1, '+2.0 pts'), item(2, '+0.0 pts'), ...Array.from({ length: 10 }, (_, n) => item(n + 3, '-1.0 pts'))]
    const keys = nbaSource([], digest, '2026-11-04', NOW).gaps.map(gap => gap.key)
    expect(keys).toEqual(['k1', ...Array.from({ length: 9 }, (_, n) => `k${n + 3}`)])
  })

  it('shows at most the hero limit of gaps, keeping the digest order and strings', () => {
    const item = (n: number): NbaSlateDigestItem => ({
      key: `k${n}`, gameId: n, playerId: n, playerName: `Player ${n}`, marketKey: 'points', market: 'Points', matchup: 'A @ B',
      when: 'x', line: '20.5', model: '22.0', gap: '+1.5 pts', gapScaled: null, gapShare: '7%',
    })
    const source = nbaSource([], Array.from({ length: 11 }, (_, n) => item(n + 1)), '2026-11-04', NOW)
    expect(source.gaps.map(gap => gap.key)).toEqual(Array.from({ length: 10 }, (_, n) => `k${n + 1}`))
    expect(source.gaps).toHaveLength(GAPS_PER_SPORT)
    expect(source.gaps[0]).toEqual({
      key: 'k1', sport: 'nba', playerName: 'Player 1', market: 'Points', matchup: 'A @ B', when: 'x', line: '20.5', model: '22.0', gap: '+1.5 pts', share: '7%',
      path: '/nba/player/1?date=2026-11-04&market=points',
    })
  })
})

describe('tennisSource', () => {
  it('counts only matches priced on both players', () => {
    const source = tennisSource([match(1, 3), match(2, 4, [null, 100]), match(3, 5, [-110, null]), match(4, 6, [null, null])], NOW)
    expect(source.gameCount).toBe(1)
    expect(source.nextGames.map(game => game.title)).toEqual(['P1 vs Q1'])
    expect(source.nextGames[0].path).toBe('/tennis/match/1')
    expect(source.propLines).toBeNull()
  })

  it('counts a match once when both date responses return it', () => {
    const source = tennisSource([match(1, 3), match(1, 3), match(2, 5)], NOW)
    expect(source.gameCount).toBe(2)
    expect(source.startsMs).toHaveLength(2)
  })

  it('is empty when nothing is priced', () => {
    expect(tennisSource([match(1, 3, [null, null])], NOW)).toMatchObject({ gameCount: 0, startsMs: [] })
  })
})

describe('isZeroGap', () => {
  it('matches a gap that shows as zero, signed or not, with or without a unit', () => {
    expect(['0.0', '+0.0', '-0.0', '+0.0 yds', ' 0.0 pts'].map(isZeroGap)).toEqual([true, true, true, true, true])
  })

  it('keeps every gap that shows a value, and a missing one', () => {
    expect(['+0.1', '-0.05', '+10.0 yds', '+0.04%', '--', '+100.0'].map(isZeroGap)).toEqual([false, false, false, false, false, false])
  })
})

describe('isPricedMatch', () => {
  it('needs both prices', () => {
    expect(isPricedMatch(match(1, 1, [-120, 100]))).toBe(true)
    expect(isPricedMatch(match(1, 1, [-120, null]))).toBe(false)
  })
})

describe('nflSource', () => {
  const nflGame = (gameId: number, hours: number, status = 'scheduled') => ({
    gameId, startUtc: at(hours), awayTeam: `A${gameId}`, homeTeam: `H${gameId}`, status, lines: [],
  }) as unknown as NflSlateGame
  const slate = (games: NflSlateGame[]) => ({ season: 2026, week: 9, gameCount: games.length, lineCount: 0, unmatchedCount: 0, games, unmatched: [] }) as NflSlateResponse

  it('groups the games still to come by Central day and names a lone game', () => {
    // NOW is Tue 11:00 CT: +56h lands on Thursday evening, +80h and +82h on Friday.
    const games = [nflGame(1, 56), nflGame(2, 80), nflGame(3, 82), nflGame(4, -3), nflGame(5, 60, 'completed')]
    const source = nflSource(slate(games), [], NOW)
    expect(source.period).toBe('Week 9')
    expect(source.gameCount).toBe(5)
    expect(source.days).toEqual([
      { key: expect.any(String), label: 'Thu', count: 1, title: 'A1 @ H1', path: '/nfl/game/1' },
      { key: expect.any(String), label: 'Fri', count: 2, title: 'A2 @ H2', path: '/nfl/game/2' },
    ])
  })

  it('has no days when nothing is left, and other sports never carry days', () => {
    expect(nflSource(slate([nflGame(1, -5)]), [], NOW).days).toEqual([])
    expect(nhlSource([nhlGame(1, 3)], NOW).days).toEqual([])
  })
})

describe('gap rows across sports', () => {
  const digestItem = (n: number, gap: string) => ({
    lineId: 100 + n, gameId: n, playerId: n, playerName: `P${n}`, market: 'Rushing yards', marketKey: 'rushing_yards',
    matchup: 'A @ B', when: 'x', line: '60.5', model: '70.1', gap, gapUnits: '+9.6 yds', gapScaled: null, gapShare: '104%', shortSample: null,
  })

  it('carries the sport, the gap in units as the slate shows it, and a player link that keeps the market and week', () => {
    const source = nflSource({ season: 2026, week: 9, gameCount: 0, lineCount: 0, unmatchedCount: 0, games: [], unmatched: [] } as NflSlateResponse, [digestItem(7, '+104.6%')], NOW)
    expect(source.gaps).toEqual([{
      key: '107', sport: 'nfl', playerName: 'P7', market: 'Rushing yards', matchup: 'A @ B', when: 'x', line: '60.5', model: '70.1', gap: '+9.6 yds', share: '104%',
      path: '/nfl/player/7?market=rushing_yards&season=2026&week=9',
    }])
  })

  it('keeps ten NFL rows in digest order and drops the rest', () => {
    const slate = { season: 2026, week: 9, gameCount: 0, lineCount: 0, unmatchedCount: 0, games: [], unmatched: [] } as NflSlateResponse
    const source = nflSource(slate, Array.from({ length: 11 }, (_, n) => digestItem(n + 1, '+1.0%')), NOW)
    expect(source.gaps.map(gap => gap.key)).toEqual(Array.from({ length: 10 }, (_, n) => String(101 + n)))
  })
})

describe('tennisGapRows', () => {
  const matches = [match(1, 3), match(2, 5)].map((entry, index) => ({ ...entry, p1Id: 10 + index * 2, p2Id: 11 + index * 2 }))
  const prop = (id: number, overrides: Partial<PropLine> = {}): PropLine => ({
    id, playerId: 10, playerName: 'P1', matchId: 1, source: 'prizepicks', statType: 'Aces', line: '4.5', oddsType: 'standard',
    fetchedAt: at(-1), startTime: at(3), pOver: 0.6, pUnder: 0.4, confidence: null, recommendation: 'OVER', statAvg: 6.0, edgePct: 33.3,
    projectionStatus: 'ok', dataQualityFlags: [], ...overrides,
  })

  it('ranks by the share of the line, one row per player, showing the gap in units, with the board link and a Central time', () => {
    const rows = tennisGapRows([
      prop(1, { edgePct: 20 }), prop(2, { statType: 'Double Faults', edgePct: -45, statAvg: 1.0, line: '2.5' }),
      prop(3, { playerId: 12, playerName: 'P2', matchId: 2, startTime: at(5), edgePct: 30 }),
    ], matches, NOW)
    expect(rows.map(row => row.key)).toEqual(['2', '3'])
    expect(rows[0]).toEqual({
      key: '2', sport: 'tennis', playerName: 'P1', market: 'Double faults', matchup: 'P1 vs Q1', when: '2:00 PM CT', line: '2.5',
      model: '1.0', gap: '-1.5', share: '45%', path: expect.stringContaining('/tennis/player/10?'),
    })
    expect([rows[1].gap, rows[1].share]).toEqual(['+1.5', '30%'])
  })

  it('keeps standard rateable lines for matches still to come and leaves the rest out', () => {
    const rows = tennisGapRows([
      prop(1, { oddsType: 'demon' }), prop(2, { source: 'draftkings' }), prop(3, { dataQualityFlags: ['no_market_total'] }),
      prop(4, { recommendation: null }), prop(5, { startTime: at(-2) }), prop(6, { projectionStatus: 'missing_stats' }),
      prop(7, { playerId: null, playerName: 'Nobody' }), prop(8, { edgePct: 12 }),
    ], matches, NOW)
    expect(rows.map(row => row.key)).toEqual(['8'])
  })

  it('leaves out a line whose gap shows as 0.0 and keeps the rest in order', () => {
    const rows = tennisGapRows([
      prop(1, { statType: 'Tie Breaks', line: '0.5', statAvg: 0.52, edgePct: 40 }),
      prop(2, { playerId: 12, playerName: 'P2', matchId: 2, startTime: at(5), edgePct: 30 }),
    ], matches, NOW)
    expect(rows.map(row => [row.key, row.gap])).toEqual([['2', '+1.5']])
  })

  it('shows at most ten rows and none for no lines', () => {
    const many = Array.from({ length: 12 }, (_, n) => prop(n + 1, { playerId: 100 + n, playerName: `X${n}`, matchId: 1, edgePct: 50 - n }))
    expect(tennisGapRows(many, matches, NOW).map(row => row.key)).toEqual(Array.from({ length: 10 }, (_, n) => String(n + 1)))
    expect(tennisGapRows([], matches, NOW)).toEqual([])
  })

  it('fills the source gaps while the cards stay the same', () => {
    const source = tennisSource(matches, NOW, [prop(1)])
    expect(source.gaps).toHaveLength(1)
    expect(source.gameCount).toBe(2)
  })
})

describe('moneyline rows', () => {
  const nflGame = (gameId: number, hours: number, model: { home: number, market: number | null } | null, status = 'scheduled') => ({
    gameId, startUtc: at(hours), awayTeam: `A${gameId}`, homeTeam: `H${gameId}`, status, lines: [],
    model: model && { modelVersion: 'nfl-elo-v1', homeElo: 0, awayElo: 0, homeWinProbability: model.home, marketHomeWinProbability: model.market, homeSpread: 0, total: 0 },
  }) as unknown as NflSlateGame
  const slate = (games: NflSlateGame[]) => ({ season: 2026, week: 9, gameCount: games.length, lineCount: 0, unmatchedCount: 0, games, unmatched: [] }) as NflSlateResponse

  it('names the NFL side the model rates above the market, largest gap first', () => {
    const rows = nflSource(slate([
      nflGame(1, 5, { home: 0.55, market: 0.6 }), nflGame(2, 6, { home: 0.7, market: 0.6 }), nflGame(3, 7, { home: 0.5, market: 0.52 }),
    ]), [], NOW).moneyline
    expect(rows.map(row => [row.key, row.side, row.gap])).toEqual([['2', 'H2', '+10.0 pp'], ['1', 'A1', '+5.0 pp'], ['3', 'A3', '+2.0 pp']])
    expect(rows[0]).toMatchObject({ sport: 'nfl', matchup: 'A2 @ H2', market: '60.0%', model: '70.0%', path: '/nfl/game/2', when: '5:00 PM CT' })
  })

  it('drops finished or started NFL games and games without a model or market probability', () => {
    const rows = nflSource(slate([
      nflGame(1, -1, { home: 0.7, market: 0.6 }), nflGame(2, 5, { home: 0.7, market: 0.6 }, 'completed'), nflGame(3, 5, null),
      nflGame(4, 5, { home: 0.7, market: null }), nflGame(5, 5, { home: 0.65, market: 0.6 }),
    ]), [], NOW).moneyline
    expect(rows.map(row => row.key)).toEqual(['5'])
  })

  it('caps each sport at ten rows', () => {
    const games = Array.from({ length: 12 }, (_, n) => nflGame(n + 1, 5, { home: 0.6 + n / 100, market: 0.5 }))
    expect(nflSource(slate(games), [], NOW).moneyline).toHaveLength(10)
  })

  it('compares the tennis ensemble with the de-vigged market and skips unpriced or unmodelled matches', () => {
    const priced = (id: number, hours: number, p1: number | null, odds: [number | null, number | null] = [-200, 170]) =>
      ({ ...match(id, hours, odds), p1WinProb: p1, p2WinProb: p1 === null ? null : 1 - p1 })
    const rows = tennisSource([priced(1, 3, 0.8), priced(2, 4, null), priced(3, 5, 0.5, [null, 100]), priced(4, -1, 0.9)], NOW).moneyline
    expect(rows).toHaveLength(1)
    expect(rows[0]).toMatchObject({ key: '1', sport: 'tennis', side: 'P1', matchup: 'P1 vs Q1', path: '/tennis/match/1', model: '80.0%' })
    expect(rows[0].market).toBe('64.3%')
    expect(rows[0].gap).toBe('+15.7 pp')
  })

  it('leaves NBA and NHL without rows', () => {
    expect(nhlSource([nhlGame(1, 3)], NOW).moneyline).toEqual([])
    expect(nbaSource([], [], '2026-11-04', NOW).moneyline).toEqual([])
  })
})

describe('tennis start reconciliation', () => {
  const line = (matchId: number, hours: number, minutes = 0): PropLine => ({
    id: matchId, playerId: null, playerName: null, matchId, source: 'prizepicks', statType: 'Aces', line: '4.5', oddsType: 'standard',
    fetchedAt: at(-1), startTime: new Date(NOW + hours * HOUR + minutes * 60000).toISOString(), pOver: null, pUnder: null, confidence: null,
  })

  it('takes the PrizePicks time only when it is a whole number of hours from the feed', () => {
    expect(reconciledStart(at(3), NOW + 4 * HOUR)).toBe(at(4))
    expect(reconciledStart(at(3), NOW + 2 * HOUR)).toBe(at(2))
    expect(reconciledStart(at(3), NOW + 3 * HOUR + 20 * 60000)).toBe(at(3))
    expect(reconciledStart(at(3), NOW + 3 * HOUR)).toBe(at(3))
    expect(reconciledStart(at(3), undefined)).toBe(at(3))
    expect(reconciledStart(null, NOW + 4 * HOUR)).toBeNull()
  })

  it('moves a mismatched match in the next start, the schedule and the moneyline rows, and leaves drifted ones alone', () => {
    const priced = (id: number, hours: number) => ({ ...match(id, hours), p1WinProb: 0.7, p2WinProb: 0.3 })
    const source = tennisSource([priced(1, 3), priced(2, 5)], NOW, [line(1, 4), line(2, 5, 20)])
    expect(source.startsMs).toEqual([NOW + 4 * HOUR, NOW + 5 * HOUR])
    expect(source.schedule.map(game => [game.key, game.when])).toEqual([['1', '3:00 PM'], ['2', '4:00 PM']])
    expect(source.moneyline.map(row => [row.key, row.when])).toEqual([['1', '3:00 PM CT'], ['2', '4:00 PM CT']])
  })
})
