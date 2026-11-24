import type { NhlLineOnlyMarket, NhlPropBoardGame } from '~/types/nhl'
import { gameState } from '~/utils/gameState'
import { compareBoardRows, propBoardPath } from '~/utils/propBoardRows'
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
  return propBoardPath('nhl', date, market)
}

/** Every NHL market, empty ones included, with rows by puck drop then player; a player's lines never merge across games. */
export function nhlPropBoard(games: readonly NhlPropBoardGame[]): NhlBoardMarket[] {
  const rowsByMarket = new Map<NhlLineOnlyMarket, NhlBoardRow[]>(NHL_LINE_ONLY_MARKETS.map(market => [market, []]))
  for (const { lines, ...game } of games) {
    for (const { market, rows } of nhlPropListGroups(lines)) {
      rowsByMarket.get(market)?.push(...rows.map(row => ({ key: `${game.gameId}:${row.key}`, game, row })))
    }
  }
  return [...rowsByMarket].map(([market, rows]) => ({ market, rows: rows.sort(compareBoardRows) }))
}

/** Null while a game is upcoming or its start is unknown. */
export function nhlBoardGameStatus(game: NhlBoardGameContext, now: Date): string | null {
  const { phase, label } = gameState(game.status, game.startUtc, now, 'Started')
  return phase === 'upcoming' ? null : label
}
