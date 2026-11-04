import type { NhlLineOnlyMarket, NhlPropBoardGame } from '~/types/nhl'
import { NHL_LINE_ONLY_MARKETS, nhlPropListGroups, type NhlPropListRow } from '~/utils/nhlLineOnly'

export type NhlBoardGameContext = Omit<NhlPropBoardGame, 'lines'>

export interface NhlBoardRow {
  key: string
  game: NhlBoardGameContext
  row: NhlPropListRow
}

export interface NhlBoardMarket {
  market: NhlLineOnlyMarket
  rows: NhlBoardRow[]
}

const DEFAULT_MARKET: NhlLineOnlyMarket = 'shots_on_goal'

/** The requested market when it is one NHL stores; otherwise the first market with rows, else Shots on Goal. */
export function nhlBoardMarket(value: string | null, groups: readonly NhlBoardMarket[]): NhlLineOnlyMarket {
  const requested = groups.find(group => group.market === value)
  return requested?.market ?? groups.find(group => group.rows.length > 0)?.market ?? DEFAULT_MARKET
}

export function nhlBoardPath(date: string | null, market: NhlLineOnlyMarket): string | null {
  if (date === null) return null
  return `/nhl/board?${new URLSearchParams({ date, market })}`
}

function dropTime(startUtc: string | null): number {
  const time = startUtc === null ? NaN : Date.parse(startUtc)
  return Number.isNaN(time) ? Infinity : time
}

function compareRows(left: NhlBoardRow, right: NhlBoardRow): number {
  const leftDrop = dropTime(left.game.startUtc)
  const rightDrop = dropTime(right.game.startUtc)
  if (leftDrop !== rightDrop) return leftDrop < rightDrop ? -1 : 1
  return left.row.playerName.localeCompare(right.row.playerName)
    || left.game.gameId - right.game.gameId
    || left.row.playerId - right.row.playerId
}

/** Every NHL market, empty ones included, with rows by puck drop then player; a player's lines never merge across games. */
export function nhlPropBoard(games: readonly NhlPropBoardGame[]): NhlBoardMarket[] {
  const rowsByMarket = new Map<NhlLineOnlyMarket, NhlBoardRow[]>(NHL_LINE_ONLY_MARKETS.map(market => [market, []]))
  for (const { lines, ...game } of games) {
    for (const { market, rows } of nhlPropListGroups(lines)) {
      rowsByMarket.get(market)?.push(...rows.map(row => ({ key: `${game.gameId}:${row.key}`, game, row })))
    }
  }
  return [...rowsByMarket].map(([market, rows]) => ({ market, rows: rows.sort(compareRows) }))
}

const TERMINAL: Record<string, string> = { completed: 'Final', postponed: 'Postponed', canceled: 'Canceled' }

/** Null while a game is upcoming or its start is unknown. */
export function nhlBoardGameStatus(game: NhlBoardGameContext, now: Date): string | null {
  return TERMINAL[game.status] ?? (dropTime(game.startUtc) <= now.getTime() ? 'Started' : null)
}
