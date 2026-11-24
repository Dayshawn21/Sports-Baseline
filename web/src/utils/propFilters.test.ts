import { describe, expect, it } from 'vitest'
import {
  ALL, gamePlayerOptions, activeGameFilter, activeGameFilters, activeTeamFilter, boardPlayerOptions, filterBoardMarkets, gamePropRowMatches, gameSideTeam, gameTeams, parseGameFilter, parseGameFilters, parsePlayerFilter, parseTeamFilter, playerNameMatches, playerOptions, playerSelected, teamAfterGames, teamMatches, visibleMarket, withPropListFilters, type BoardFilter,
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
})

describe('filterBoardMarkets', () => {
  const nyk = { gameId: 12, awayTeam: 'BOS', homeTeam: 'NYK' }
  const gsw = { gameId: 13, awayTeam: 'LAL', homeTeam: 'GSW' }
  const okc = { gameId: 14, awayTeam: 'OKC', homeTeam: 'POR' }
  const row = (game: typeof nyk, playerName: string, team: string | null) => ({ game, row: { playerName, team } })
  const markets = [
    { market: 'points', rows: [row(nyk, 'Jalen Brunson', 'NYK'), row(nyk, 'Jaylen Brown', 'BOS'), row(gsw, 'Luka Dončić', 'LAL'), row(okc, 'Chet Holmgren', 'OKC')] },
    { market: 'assists', rows: [row(gsw, 'Stephen Curry', 'GS'), row(gsw, 'Unlinked Player', null)] },
  ]
  const none: BoardFilter = { players: [], team: ALL, games: [] }
  const names = (filter: Partial<BoardFilter>) => filterBoardMarkets(markets, { ...none, ...filter })
    .map(market => market.rows.map(item => item.row.playerName))

  it('returns the same markets when nothing is filtered', () => {
    expect(filterBoardMarkets(markets, none)).toBe(markets)
  })

  it('shows every chosen player and keeps emptied markets', () => {
    expect(names({ players: ['Luka Dončić', 'Jaylen Brown'] })).toEqual([['Jaylen Brown', 'Luka Dončić'], []])
    expect(names({ players: ['Stephen Curry'] })).toEqual([[], ['Stephen Curry']])
  })

  it('filters by team through the row game, reading a provider code as its game code', () => {
    expect(names({ team: 'GSW' })).toEqual([[], ['Stephen Curry']])
  })

  it('leaves a null team out of a specific team but not out of a player pick', () => {
    expect(names({ team: 'LAL' })).toEqual([['Luka Dončić'], []])
    expect(names({ players: ['Unlinked Player'] })).toEqual([[], ['Unlinked Player']])
  })

  it('shows every chosen game', () => {
    expect(names({ games: ['12', '14'] })).toEqual([['Jalen Brunson', 'Jaylen Brown', 'Chet Holmgren'], []])
  })

  it('needs a row to match the player, the team and a game', () => {
    expect(names({ games: ['12'], team: 'BOS', players: ['Jaylen Brown', 'Jalen Brunson'] })).toEqual([['Jaylen Brown'], []])
    expect(names({ games: ['13'], players: ['Jaylen Brown'] })).toEqual([[], []])
  })

  it('lists picker options under the team and games, keeping chosen names', () => {
    expect(boardPlayerOptions(markets, { ...none, team: 'BOS' })).toEqual(['Jaylen Brown'])
    expect(boardPlayerOptions(markets, { ...none, games: ['14'], players: ['Jaylen Brown'] })).toEqual(['Chet Holmgren', 'Jaylen Brown'])
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
    expect(gamePropRowMatches(row('Trevor Lawrence', 'JAC'), game, { players: [], team: 'JAX' })).toBe(true)
    expect(gamePropRowMatches(row('Trevor Lawrence', 'JAC'), game, { players: [], team: 'TEN' })).toBe(false)
  })

  it('needs both the team and the search', () => {
    expect(gamePropRowMatches(row('Cam Ward', 'TEN'), game, { players: ['Cam Ward', 'Tyler Allgeier'], team: 'TEN' })).toBe(true)
    expect(gamePropRowMatches(row('Cam Ward', 'TEN'), game, { players: ['Trevor Lawrence'], team: 'TEN' })).toBe(false)
  })

  it('leaves a null team under all teams only', () => {
    expect(gamePropRowMatches(row('Unlinked', null), game, { players: [], team: ALL })).toBe(true)
    expect(gamePropRowMatches(row('Unlinked', null), game, { players: [], team: 'TEN' })).toBe(false)
  })
})

describe('list filters in the URL', () => {
  const params = (query: string) => new URLSearchParams(query)

  it('reads repeated players, trimmed and without duplicates', () => {
    expect(parsePlayerFilter(params('player=Joe+Burrow&player=+Tee+Higgins+&player=Joe+Burrow&player=+'))).toEqual(['Joe Burrow', 'Tee Higgins'])
    expect(parsePlayerFilter(params(''))).toEqual([])
  })

  it('caps the name length and the number of players', () => {
    expect(parsePlayerFilter(params(`player=${'x'.repeat(100)}`))[0]).toHaveLength(64)
    const many = Array.from({ length: 30 }, (_, index) => `player=P${index}`).join('&')
    expect(parsePlayerFilter(params(many))).toHaveLength(20)
  })

  it('keeps only valid unique game ids', () => {
    expect(parseGameFilters(params('game=12&game=x&game=0&game=12&game=13'))).toEqual(['12', '13'])
  })

  it('drops games that are not in this period', () => {
    expect(activeGameFilters(['12', '99'], [{ gameId: 12 }])).toEqual(['12'])
  })

  it('writes lists as repeated keys and leaves other params alone', () => {
    const next = withPropListFilters(params('date=2026-11-10&market=points&game=9'), { player: ['Joe Burrow', 'Tee Higgins'], game: [], team: 'CIN' })

    expect(next.toString()).toBe('date=2026-11-10&market=points&player=Joe+Burrow&player=Tee+Higgins&team=CIN')
  })

  it('drops all teams and round trips through parsing', () => {
    const next = withPropListFilters(params('team=CIN'), { player: ['Luka Dončić'], game: ['12', '13'], team: ALL })

    expect(next.has('team')).toBe(false)
    expect(parsePlayerFilter(next)).toEqual(['Luka Dončić'])
    expect(parseGameFilters(next)).toEqual(['12', '13'])
  })
})

describe('playerSelected', () => {
  it('matches everyone on an empty selection', () => {
    expect(playerSelected('Anyone', [])).toBe(true)
    expect(playerSelected(null, [])).toBe(true)
  })

  it('matches only chosen names, whole name not part of it', () => {
    expect(playerSelected('Jaylen Brown', ['Jaylen Brown', 'Joel Embiid'])).toBe(true)
    expect(playerSelected('Chase Brown', ['Jaylen Brown'])).toBe(false)
    expect(playerSelected('Brown', ['Jaylen Brown'])).toBe(false)
    expect(playerSelected(null, ['Jaylen Brown'])).toBe(false)
  })

  it('ignores accents and punctuation between sources', () => {
    expect(playerSelected('Luka Doncic', ['Luka Dončić'])).toBe(true)
    expect(playerSelected('AJ Brown', ['A.J. Brown'])).toBe(true)
  })
})

describe('playerOptions', () => {
  it('sorts and lists each player once, across spellings', () => {
    expect(playerOptions(['Zed', 'Amy', 'Zed', null, '', 'Luka Dončić', 'Luka Doncic'], [])).toEqual(['Amy', 'Luka Dončić', 'Zed'])
  })

  it('keeps a chosen name that has no rows', () => {
    expect(playerOptions(['Amy'], ['Bo'])).toEqual(['Amy', 'Bo'])
  })
})

describe('teamAfterGames', () => {
  const games = [{ gameId: 12, awayTeam: 'BOS', homeTeam: 'NYK' }, { gameId: 13, awayTeam: 'LAL', homeTeam: 'GSW' }]

  it('keeps a team playing in any chosen game', () => {
    expect(teamAfterGames('LAL', ['12', '13'], games)).toBe('LAL')
  })

  it('clears a team playing in none of them', () => {
    expect(teamAfterGames('LAL', ['12'], games)).toBe(ALL)
  })

  it('keeps the team when no game is chosen', () => {
    expect(teamAfterGames('LAL', [], games)).toBe('LAL')
  })
})

describe('gamePlayerOptions', () => {
  const game = { awayTeam: 'JAX', homeTeam: 'TEN' }
  const rows = [{ playerName: 'Trevor Lawrence', team: 'JAC' }, { playerName: 'Cam Ward', team: 'TEN' }, { playerName: 'Trevor Lawrence', team: 'JAC' }]

  it('lists each player once', () => {
    expect(gamePlayerOptions(rows, game, { players: [], team: ALL })).toEqual(['Cam Ward', 'Trevor Lawrence'])
  })

  it('narrows to the chosen side and keeps chosen names', () => {
    expect(gamePlayerOptions(rows, game, { players: [], team: 'JAX' })).toEqual(['Trevor Lawrence'])
    expect(gamePlayerOptions(rows, game, { players: ['Cam Ward'], team: 'JAX' })).toEqual(['Cam Ward', 'Trevor Lawrence'])
  })
})
