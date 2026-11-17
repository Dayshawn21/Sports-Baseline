import type { NbaPropBoardGame } from '~/types/nba'
import { NBA_LINE_ONLY_MARKETS, nbaLineOnlyGroups, type NbaLineOnlyRow } from '~/utils/nbaLineOnly'
import { nbaPropGroups, type NbaPropCard } from '~/utils/nbaProps'
import { CENTRAL_TZ } from '~/utils/format'
import { gameState } from '~/utils/gameState'
import { boardStartTime, compareBoardRows, propBoardPath } from '~/utils/propBoardRows'

export type NbaBoardGameContext = Omit<NbaPropBoardGame, 'lines' | 'lineOnlyLines'>

interface BoardRowContext {
  key: string
  game: NbaBoardGameContext
}

export type NbaBoardRow = BoardRowContext & (
  { kind: 'modelled', row: NbaPropCard } |
  { kind: 'line-only', row: NbaLineOnlyRow }
)

export interface NbaBoardMarket {
  market: string
  rows: NbaBoardRow[]
}

export function nbaBoardMarket(value: string | null, markets: NbaBoardMarket[]): string {
  return value !== null && markets.some(group => group.market === value) ? value : 'points'
}

export function nbaBoardPath(date: string | null, market: string): string | null {
  return propBoardPath('nba', date, market)
}

const TIP_FORMAT = new Intl.DateTimeFormat('en-US', {
  timeZone: CENTRAL_TZ, weekday: 'short', hour: 'numeric', minute: '2-digit',
})

export function nbaBoardGameLabels(game: NbaBoardGameContext, now: Date): { tip: string, status: string | null } {
  const time = boardStartTime(game.startUtc)
  const tip = Number.isFinite(time) ? `${TIP_FORMAT.format(time)} CT` : 'Tip time not set'
  const { phase, label } = gameState(game.status, game.startUtc, now, 'Tipped off')
  return { tip, status: phase === 'upcoming' ? null : label }
}

function compareRows(left: NbaBoardRow, right: NbaBoardRow): number {
  return compareBoardRows(left, right) || left.kind.localeCompare(right.kind)
}

/** Group within each game so a player's lines from different games never merge. */
export function nbaPropBoard(games: NbaPropBoardGame[]): NbaBoardMarket[] {
  const markets = new Map<string, NbaBoardRow[]>(NBA_LINE_ONLY_MARKETS.map(market => [market, []]))
  for (const { lines, lineOnlyLines, ...game } of games) {
    for (const { market, cards } of nbaPropGroups(lines)) {
      const rows = markets.get(market) ?? []
      rows.push(...cards.map(row => ({
        key: `modelled:${game.gameId}:${market}:${row.playerId}`,
        kind: 'modelled' as const, game, row,
      })))
      markets.set(market, rows)
    }
    for (const { market, rows: grouped } of nbaLineOnlyGroups(lineOnlyLines)) {
      const rows = markets.get(market) ?? []
      rows.push(...grouped.map(row => ({
        key: `line-only:${game.gameId}:${market}:${row.playerId}`,
        kind: 'line-only' as const, game, row,
      })))
      markets.set(market, rows)
    }
  }
  return [...markets].map(([market, rows]) => ({ market, rows: rows.sort(compareRows) }))
}
