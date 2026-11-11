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

/** Keeps a trailing space, so the box stays typable when the URL is its only state. */
export function parsePlayerQuery(value: string | null): string {
  return (value ?? '').trimStart().slice(0, MAX_QUERY_LENGTH)
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

/** Choosing a game keeps the team only when it plays in that game, so the two filters cannot empty the board. */
export function teamAfterGame(team: string, game: string, games: readonly FilterGame[]): string {
  const chosen = games.find(item => String(item.gameId) === game)
  return !chosen || team === chosen.awayTeam || team === chosen.homeTeam ? team : ALL
}

export interface BoardFilter {
  q: string
  team: string
  game: string
}

export function isFiltering(filter: BoardFilter): boolean {
  return filter.q.trim() !== '' || filter.team !== ALL || filter.game !== ALL
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
    rows: market.rows.filter(({ game, row }) => (filter.game === ALL || String(game.gameId) === filter.game)
      && teamMatches(gameSideTeam(row.team, game), filter.team)
      && playerNameMatches(row.playerName, filter.q)),
  }))
}

/** The market to show. While filtering, an emptied market gives way to one with rows; the URL keeps the user's choice. */
export function visibleMarket<M>(selected: M, markets: ReadonlyArray<{ market: M, count: number }>, filtering: boolean): M {
  if (!filtering || markets.find(item => item.market === selected)?.count) return selected
  return markets.find(item => item.count > 0)?.market ?? selected
}

export interface PropFilterPatch {
  q?: string
  team?: string
  game?: string
}

/** A copy of the params with these filters applied; a blank or 'all' value drops its key. */
export function withPropFilters(params: URLSearchParams, patch: PropFilterPatch): URLSearchParams {
  const next = new URLSearchParams(params)
  for (const [key, value] of Object.entries(patch)) {
    if (value.trim() === '' || value === ALL) next.delete(key)
    else next.set(key, value)
  }
  return next
}

export interface GamePropFilter {
  q: string
  team: string
}

export function gamePropRowMatches(row: { playerName: string, team: string | null }, game: { awayTeam: string, homeTeam: string }, filter: GamePropFilter): boolean {
  return teamMatches(gameSideTeam(row.team, game), filter.team) && playerNameMatches(row.playerName, filter.q)
}
