import { describe, expect, it } from 'vitest'
import type { NflSlateGame, NflSlateResponse } from '~/types/nfl'
import type { MatchPrediction } from '~/types/tennis'
import type { NhlSlateGame } from '~/types/nhl'
import { GAPS_PER_SPORT, HERO_NEXT_LIMIT, crossSportGaps, isPricedMatch, nbaSource, nflSource, nhlSource, tennisSource } from '~/utils/homeSources'
import type { NbaSlateDigestItem } from '~/utils/nbaSlate'

const HOUR = 60 * 60 * 1000
// Tue 2026-11-03 17:00 UTC = 11:00 CT.
const NOW = Date.UTC(2026, 10, 3, 17, 0)
const at = (hours: number) => new Date(NOW + hours * HOUR).toISOString()

function nhlGame(gameId: number, hours: number | null, status = 'scheduled'): NhlSlateGame {
  return {
    gameId, season: 2026, week: null, gameType: 'REG', gameDate: '2026-11-03', startUtc: hours === null ? null : at(hours), status,
    awayTeam: `A${gameId}`, homeTeam: `H${gameId}`, awayTeamName: '', homeTeamName: '', awayScore: null, homeScore: null,
    endPeriod: null, propLineCount: 10, moneyline: null, spread: null, total: null,
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

  it('is empty for no games', () => {
    expect(nhlSource([], NOW)).toMatchObject({ gameCount: 0, startsMs: [], nextGames: [] })
  })

  it('leaves a started game out of the next list but keeps it in the count', () => {
    const source = nhlSource([nhlGame(1, -1), nhlGame(2, 2)], NOW)
    expect(source.gameCount).toBe(2)
    expect(source.nextGames.map(game => game.key)).toEqual(['2'])
  })
})

describe('nbaSource', () => {
  it('shows at most the hero limit of gaps, keeping the digest order and strings', () => {
    const item = (n: number): NbaSlateDigestItem => ({
      key: `k${n}`, gameId: n, playerId: n, playerName: `Player ${n}`, marketKey: 'points', market: 'Points', matchup: 'A @ B',
      when: 'x', line: '20.5', model: '22.0', gap: '+1.5 · +7%',
    })
    const source = nbaSource([], [1, 2, 3, 4, 5].map(item), '2026-11-04', NOW)
    expect(source.gaps.map(gap => gap.key)).toEqual(['k1', 'k2', 'k3'])
    expect(source.gaps).toHaveLength(GAPS_PER_SPORT)
    expect(source.gaps[0]).toEqual({
      key: 'k1', sport: 'nba', playerName: 'Player 1', market: 'Points', matchup: 'A @ B', line: '20.5', model: '22.0', gap: '+1.5 · +7%',
      path: '/nba/player/1?date=2026-11-04&market=points',
    })
  })
})

describe('tennisSource', () => {
  it('counts only matches priced on both players', () => {
    const source = tennisSource([match(1, 3), match(2, 4, [null, 100]), match(3, 5, [-110, null]), match(4, 6, [null, null])], NOW)
    expect(source.gameCount).toBe(1)
    expect(source.nextGames.map(game => game.title)).toEqual(['P1 vs Q1'])
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
      { key: expect.any(String), label: 'Thu', count: 1, title: 'A1 @ H1' },
      { key: expect.any(String), label: 'Fri', count: 2, title: 'A2 @ H2' },
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
    matchup: 'A @ B', when: 'x', line: '60.5', model: '70.1', gap,
  })

  it('carries the sport, the model value and a player link that keeps the market and week', () => {
    const source = nflSource({ season: 2026, week: 9, gameCount: 0, lineCount: 0, unmatchedCount: 0, games: [], unmatched: [] } as NflSlateResponse, [digestItem(7, '+104.6%')], NOW)
    expect(source.gaps).toEqual([{
      key: '107', sport: 'nfl', playerName: 'P7', market: 'Rushing yards', matchup: 'A @ B', line: '60.5', model: '70.1', gap: '+104.6%',
      path: '/nfl/player/7?market=rushing_yards&season=2026&week=9',
    }])
  })

  it('takes three rows per sport, NFL then NBA, and never sorts across sports', () => {
    const slate = { season: 2026, week: 9, gameCount: 0, lineCount: 0, unmatchedCount: 0, games: [], unmatched: [] } as NflSlateResponse
    const nfl = nflSource(slate, [1, 2, 3, 4].map(n => digestItem(n, '+1.0%')), NOW)
    const nbaItem = (n: number): NbaSlateDigestItem => ({
      key: `n${n}`, gameId: n, playerId: n, playerName: `N${n}`, marketKey: 'points', market: 'Points', matchup: 'A @ B',
      when: 'x', line: '20.5', model: '30.0', gap: '+9.5 · +46%',
    })
    const nba = nbaSource([], [1, 2, 3, 4].map(nbaItem), '2026-11-04', NOW)
    expect(crossSportGaps(nfl, nba).map(gap => gap.key)).toEqual(['101', '102', '103', 'n1', 'n2', 'n3'])
  })

  it('has no rows when neither sport has gaps', () => {
    expect(crossSportGaps(nhlSource([], NOW), nhlSource([], NOW))).toEqual([])
  })
})
