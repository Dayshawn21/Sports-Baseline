import { describe, expect, it } from 'vitest'
import {
  ALL, activeGameFilter, activeTeamFilter, filterBoardMarkets, gamePropRowMatches, gameSideTeam, gameTeams, parseGameFilter, parsePlayerQuery, parseTeamFilter, playerNameMatches, teamAfterGame, teamMatches, visibleMarket, withPropFilters, type BoardFilter,
} from '~/utils/propFilters'

describe('playerNameMatches', () => {
  it.each([
    ['Luka Dončić', 'doncic'],
    ['Novak Đoković', 'dokovic'],
    ['Martin Ødegaard', 'odegaard'],
    ['A.J. Brown', 'aj brown'],
    ['A.J. Brown', 'brown aj'],
    ["De'Aaron Fox", 'deaaron'],
    ['Jaxon Smith-Njigba', 'smith njigba'],
    ['Patrick Mahomes', 'MAHO'],
  ])('finds %s with %s', (name, query) => {
    expect(playerNameMatches(name, query)).toBe(true)
  })

  it('needs every word of the query', () => {
    expect(playerNameMatches('A.J. Brown', 'aj green')).toBe(false)
  })

  it('matches everyone on an empty or punctuation-only query', () => {
    expect(playerNameMatches('Anyone', '')).toBe(true)
    expect(playerNameMatches(null, '  ')).toBe(true)
    expect(playerNameMatches('Anyone', '...')).toBe(true)
  })

  it('does not match a missing name on a real query', () => {
    expect(playerNameMatches(null, 'brown')).toBe(false)
  })
})

describe('teamMatches', () => {
  it('lets every row through under all teams, a null team included', () => {
    expect(teamMatches('KC', ALL)).toBe(true)
    expect(teamMatches(null, ALL)).toBe(true)
  })

  it('matches only that team under a specific filter', () => {
    expect(teamMatches('KC', 'KC')).toBe(true)
    expect(teamMatches('BUF', 'KC')).toBe(false)
    expect(teamMatches(null, 'KC')).toBe(false)
  })
})

describe('gameSideTeam', () => {
  const game = (awayTeam: string, homeTeam: string) => ({ awayTeam, homeTeam })

  it('keeps an exact code', () => {
    expect(gameSideTeam('KC', game('BUF', 'KC'))).toBe('KC')
  })

  it.each([
    ['JAC', 'JAX', 'TEN', 'JAX'],
    ['LAR', 'SEA', 'LA', 'LA'],
    ['WSH', 'WAS', 'DAL', 'WAS'],
    ['TB', 'TBL', 'BOS', 'TBL'],
  ])('reads provider code %s in %s at %s as %s', (team, away, home, expected) => {
    expect(gameSideTeam(team, game(away, home))).toBe(expected)
  })

  it('stays null on a null team, a tie, or no shared prefix', () => {
    expect(gameSideTeam(null, game('BUF', 'KC'))).toBeNull()
    expect(gameSideTeam('BKN', game('BRK', 'BOS'))).toBeNull()
    expect(gameSideTeam('ZZZ', game('BUF', 'KC'))).toBeNull()
  })
})

describe('gameTeams', () => {
  it('lists each team once, sorted', () => {
    expect(gameTeams([{ awayTeam: 'KC', homeTeam: 'BUF' }, { awayTeam: 'DAL', homeTeam: 'KC' }])).toEqual(['BUF', 'DAL', 'KC'])
  })
})

describe('URL values', () => {
  it('keeps a trailing space while typing and caps the length', () => {
    expect(parsePlayerQuery('  aj ')).toBe('aj ')
    expect(parsePlayerQuery(null)).toBe('')
    expect(parsePlayerQuery('x'.repeat(100))).toHaveLength(64)
  })

  it('reads only a team code as a team', () => {
    expect(parseTeamFilter('KC')).toBe('KC')
    expect(parseTeamFilter('kc')).toBe(ALL)
    expect(parseTeamFilter('<b>')).toBe(ALL)
    expect(parseTeamFilter(null)).toBe(ALL)
  })

  it('drops a team that is not in this period', () => {
    expect(activeTeamFilter('KC', ['BUF', 'KC'])).toBe('KC')
    expect(activeTeamFilter('DAL', ['BUF', 'KC'])).toBe(ALL)
  })

  it('sets and drops keys without touching the others', () => {
    const params = new URLSearchParams('date=2026-11-10&q=aj&team=KC')

    expect(withPropFilters(params, { q: 'luka', team: ALL, game: '12' }).toString()).toBe('date=2026-11-10&q=luka&game=12')
    expect(withPropFilters(params, { q: '   ' }).toString()).toBe('date=2026-11-10&team=KC')
    expect(params.toString()).toBe('date=2026-11-10&q=aj&team=KC')
  })
})

describe('game filter', () => {
  const games = [{ gameId: 12, awayTeam: 'BOS', homeTeam: 'NYK' }, { gameId: 13, awayTeam: 'LAL', homeTeam: 'GSW' }]

  it('reads only a positive id', () => {
    expect(parseGameFilter('12')).toBe('12')
    expect(parseGameFilter('0')).toBe(ALL)
    expect(parseGameFilter('12x')).toBe(ALL)
    expect(parseGameFilter(null)).toBe(ALL)
  })

  it('drops a game that is not in this period', () => {
    expect(activeGameFilter('13', games)).toBe('13')
    expect(activeGameFilter('99', games)).toBe(ALL)
  })

  it('keeps a team only when it plays in the chosen game', () => {
    expect(teamAfterGame('BOS', '12', games)).toBe('BOS')
    expect(teamAfterGame('LAL', '12', games)).toBe(ALL)
    expect(teamAfterGame('LAL', ALL, games)).toBe('LAL')
  })
})

describe('filterBoardMarkets', () => {
  const nyk = { gameId: 12, awayTeam: 'BOS', homeTeam: 'NYK' }
  const gsw = { gameId: 13, awayTeam: 'LAL', homeTeam: 'GSW' }
  const row = (game: typeof nyk, playerName: string, team: string | null) => ({ game, row: { playerName, team } })
  const markets = [
    { market: 'points', rows: [row(nyk, 'Jalen Brunson', 'NYK'), row(nyk, 'Jaylen Brown', 'BOS'), row(gsw, 'Luka Dončić', 'LAL')] },
    { market: 'assists', rows: [row(gsw, 'Stephen Curry', 'GS'), row(gsw, 'Unlinked Player', null)] },
  ]
  const names = (filter: Partial<BoardFilter>) => filterBoardMarkets(markets, { q: '', team: ALL, game: ALL, ...filter })
    .map(market => market.rows.map(item => item.row.playerName))

  it('returns the same markets when nothing is filtered', () => {
    expect(filterBoardMarkets(markets, { q: ' ', team: ALL, game: ALL })).toBe(markets)
  })

  it('keeps emptied markets so the pills stay put', () => {
    expect(names({ q: 'doncic' })).toEqual([['Luka Dončić'], []])
  })

  it('filters by team through the row game, reading a provider code as its game code', () => {
    expect(names({ team: 'GSW' })).toEqual([[], ['Stephen Curry']])
  })

  it('leaves a null team out of a specific team but not out of search', () => {
    expect(names({ team: 'LAL' })).toEqual([['Luka Dončić'], []])
    expect(names({ q: 'unlinked' })).toEqual([[], ['Unlinked Player']])
  })

  it('filters by game and combines every filter', () => {
    expect(names({ game: '12' })).toEqual([['Jalen Brunson', 'Jaylen Brown'], []])
    expect(names({ game: '12', team: 'BOS', q: 'brown' })).toEqual([['Jaylen Brown'], []])
  })
})

describe('visibleMarket', () => {
  const markets = [{ market: 'points', count: 0 }, { market: 'assists', count: 2 }, { market: 'rebounds', count: 1 }]

  it('keeps the selected market when not filtering', () => {
    expect(visibleMarket('points', markets, false)).toBe('points')
  })

  it('keeps the selected market when it has rows', () => {
    expect(visibleMarket('rebounds', markets, true)).toBe('rebounds')
  })

  it('moves to the first market with rows when filtering empties the selected one', () => {
    expect(visibleMarket('points', markets, true)).toBe('assists')
  })

  it('stays put when no market has rows', () => {
    expect(visibleMarket('points', [{ market: 'points', count: 0 }], true)).toBe('points')
  })
})

describe('gamePropRowMatches', () => {
  const game = { awayTeam: 'JAX', homeTeam: 'TEN' }
  const row = (playerName: string, team: string | null) => ({ playerName, team })

  it('reads a provider code as the game side', () => {
    expect(gamePropRowMatches(row('Trevor Lawrence', 'JAC'), game, { q: '', team: 'JAX' })).toBe(true)
    expect(gamePropRowMatches(row('Trevor Lawrence', 'JAC'), game, { q: '', team: 'TEN' })).toBe(false)
  })

  it('needs both the team and the search', () => {
    expect(gamePropRowMatches(row('Cam Ward', 'TEN'), game, { q: 'ward', team: 'TEN' })).toBe(true)
    expect(gamePropRowMatches(row('Cam Ward', 'TEN'), game, { q: 'lawrence', team: 'TEN' })).toBe(false)
  })

  it('leaves a null team under all teams only', () => {
    expect(gamePropRowMatches(row('Unlinked', null), game, { q: '', team: ALL })).toBe(true)
    expect(gamePropRowMatches(row('Unlinked', null), game, { q: '', team: 'TEN' })).toBe(false)
  })
})
