export const ALL = 'all'

const MAX_QUERY_LENGTH = 64

// NFD leaves these whole, so stripping marks alone would not reach them.
const UNSPLIT_LETTERS: Record<string, string> = { đ: 'd', ð: 'd', ø: 'o', ł: 'l', ß: 'ss', æ: 'ae', œ: 'oe', ı: 'i' }

function searchForm(value: string): string {
  return value.toLowerCase()
    .replace(/[đðøłßæœı]/g, letter => UNSPLIT_LETTERS[letter])
    .normalize('NFD')
    .replace(/\p{M}/gu, '')
    .replace(/[.'’`]/g, '')
    .replace(/[^\p{L}\p{N}]+/gu, ' ')
    .trim()
}

export function playerNameMatches(name: string | null | undefined, query: string): boolean {
  const words = searchForm(query).split(' ').filter(Boolean)
  if (words.length === 0) return true
  const target = searchForm(name ?? '')
  return words.every(word => target.includes(word))
}

export function teamMatches(team: string | null, filter: string): boolean {
  return filter === ALL || team === filter
}

function sharedPrefixLength(left: string, right: string): number {
  let length = 0
  while (length < left.length && left[length] === right[length]) length += 1
  return length
}

/**
 * The row's team as one of its game's two codes. Rows carry PrizePicks' code and games the
 * schedule source's, which disagree (`JAC` and `JAX`). A row belongs to this game, so the
 * closer code is its team; a tie stays null rather than guessing.
 */
export function gameSideTeam(team: string | null, game: { awayTeam: string, homeTeam: string }): string | null {
  if (team === null) return null
  if (team === game.awayTeam || team === game.homeTeam) return team
  const away = sharedPrefixLength(team, game.awayTeam)
  const home = sharedPrefixLength(team, game.homeTeam)
  if (away === home) return null
  return away > home ? game.awayTeam : game.homeTeam
}

export function gameTeams(games: ReadonlyArray<{ awayTeam: string, homeTeam: string }>): string[] {
  return [...new Set(games.flatMap(game => [game.awayTeam, game.homeTeam]))].sort()
}

export function parseTeamFilter(value: string | null): string {
  return value !== null && /^[A-Z]{2,4}$/.test(value) ? value : ALL
}

/** A team from an old link that is not playing in this period reads as no filter. */
export function activeTeamFilter(filter: string, teams: readonly string[]): string {
  return teams.includes(filter) ? filter : ALL
}

export function parseGameFilter(value: string | null): string {
  return value !== null && /^[1-9]\d{0,15}$/.test(value) ? value : ALL
}

interface FilterGame {
  gameId: number
  awayTeam: string
  homeTeam: string
}

export function activeGameFilter(filter: string, games: ReadonlyArray<Pick<FilterGame, 'gameId'>>): string {
  return games.some(game => String(game.gameId) === filter) ? filter : ALL
}

export interface BoardFilter {
  players: string[]
  team: string
  games: string[]
}

export function isFiltering(filter: BoardFilter): boolean {
  return filter.players.length > 0 || filter.team !== ALL || filter.games.length > 0
}

interface FilterableBoardRow {
  game: FilterGame
  row: { playerName: string, team: string | null }
}

/** Every market stays, emptied ones included, so the pills do not reshuffle as a filter narrows them. */
export function filterBoardMarkets<R extends FilterableBoardRow, M extends { rows: R[] }>(markets: M[], filter: BoardFilter): M[] {
  if (!isFiltering(filter)) return markets
  return markets.map(market => ({
    ...market,
    rows: market.rows.filter(({ game, row }) => (filter.games.length === 0 || filter.games.includes(String(game.gameId)))
      && teamMatches(gameSideTeam(row.team, game), filter.team)
      && playerSelected(row.playerName, filter.players)),
  }))
}

/** The picker lists players under the current team and games, so choosing Boston lists Boston players. */
export function boardPlayerOptions<R extends FilterableBoardRow, M extends { rows: R[] }>(markets: M[], filter: BoardFilter): string[] {
  return playerOptions(filterBoardMarkets(markets, { ...filter, players: [] }).flatMap(market => market.rows.map(item => item.row.playerName)), filter.players)
}

/** The market to show. While filtering, an emptied market gives way to one with rows; the URL keeps the user's choice. */
export function visibleMarket<M>(selected: M, markets: ReadonlyArray<{ market: M, count: number }>, filtering: boolean): M {
  if (!filtering || markets.find(item => item.market === selected)?.count) return selected
  return markets.find(item => item.count > 0)?.market ?? selected
}

export interface GamePropFilter {
  players: string[]
  team: string
}

export function gamePropRowMatches(row: { playerName: string, team: string | null }, game: { awayTeam: string, homeTeam: string }, filter: GamePropFilter): boolean {
  return teamMatches(gameSideTeam(row.team, game), filter.team) && playerSelected(row.playerName, filter.players)
}

const MAX_PLAYERS = 20

export function parsePlayerFilter(params: URLSearchParams): string[] {
  const names = params.getAll('player').map(name => name.trim().slice(0, MAX_QUERY_LENGTH)).filter(Boolean)
  return [...new Set(names)].slice(0, MAX_PLAYERS)
}

export function parseGameFilters(params: URLSearchParams): string[] {
  return [...new Set(params.getAll('game').filter(value => parseGameFilter(value) !== ALL))]
}

export function activeGameFilters(selected: readonly string[], games: ReadonlyArray<Pick<FilterGame, 'gameId'>>): string[] {
  return selected.filter(game => activeGameFilter(game, games) !== ALL)
}

/** An empty selection means no player filter. Names compare by search form, so one source's accents still match another's. */
export function playerSelected(name: string | null | undefined, players: readonly string[]): boolean {
  if (players.length === 0) return true
  const target = searchForm(name ?? '')
  return players.some(player => searchForm(player) === target)
}

/** Chosen names always stay listed, so a chip keeps its label when another filter hides that player's rows. */
export function playerOptions(names: Iterable<string | null | undefined>, players: readonly string[]): string[] {
  const options = new Map<string, string>()
  for (const name of [...names, ...players]) {
    if (!name) continue
    const key = searchForm(name)
    if (key && !options.has(key)) options.set(key, name)
  }
  return [...options.values()].sort((left, right) => left.localeCompare(right))
}

/** Choosing games keeps the team only when it plays in one of them. */
export function teamAfterGames(team: string, selected: readonly string[], games: readonly FilterGame[]): string {
  if (selected.length === 0) return team
  const chosen = games.filter(game => selected.includes(String(game.gameId)))
  return chosen.length === 0 || chosen.some(game => team === game.awayTeam || team === game.homeTeam) ? team : ALL
}

export interface PropListFilterPatch {
  player?: readonly string[]
  game?: readonly string[]
  team?: string
}

/** A copy of the params with these filters applied, lists as repeated keys; an empty list or 'all' drops its key. */
export function withPropListFilters(params: URLSearchParams, patch: PropListFilterPatch): URLSearchParams {
  const next = new URLSearchParams(params)
  for (const [key, value] of Object.entries(patch)) {
    next.delete(key)
    for (const item of typeof value === 'string' ? [value] : value) {
      if (item !== ALL) next.append(key, item)
    }
  }
  return next
}

/** The picker lists players on the chosen side, always keeping names already chosen. */
export function gamePlayerOptions(rows: ReadonlyArray<{ playerName: string, team: string | null }>, game: { awayTeam: string, homeTeam: string }, filter: GamePropFilter): string[] {
  return playerOptions(rows.filter(row => gamePropRowMatches(row, game, { ...filter, players: [] })).map(row => row.playerName), filter.players)
}
