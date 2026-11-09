interface LogGame { gameDate: string, opponent: string | null, value: number | null }
interface LogMarket { market: string, recent: readonly LogGame[] }

export interface PlayerGameLogRow {
  gameDate: string
  opponent: string | null
  /** One per column, in column order; null when that market has no value for the game. */
  values: (number | null)[]
}

export interface PlayerGameLog {
  columns: string[]
  rows: PlayerGameLogRow[]
}

export interface PlayerFormAverage {
  market: string
  average: number
  games: number
}

/** Each market's recent games joined by date into one table, newest first, columns in `order`; markets not in `order` are left out. */
export function playerGameLog(markets: readonly LogMarket[], order: readonly string[], limit = 10): PlayerGameLog {
  const columns = order.filter(market => markets.some(item => item.market === market && item.recent.length > 0))
  const byDate = new Map<string, PlayerGameLogRow>()
  for (const market of markets) {
    const column = columns.indexOf(market.market)
    if (column === -1) continue
    for (const game of market.recent) {
      const row = byDate.get(game.gameDate) ?? { gameDate: game.gameDate, opponent: game.opponent, values: columns.map(() => null) }
      row.opponent ??= game.opponent
      row.values[column] = game.value
      byDate.set(game.gameDate, row)
    }
  }
  const rows = [...byDate.values()].sort((left, right) => right.gameDate.localeCompare(left.gameDate)).slice(0, limit)
  return { columns, rows }
}

/** Each column's mean over the games in the log that have a value. */
export function playerFormAverages(log: PlayerGameLog): PlayerFormAverage[] {
  return log.columns.flatMap((market, column) => {
    const values = log.rows.flatMap(row => row.values[column] ?? [])
    return values.length === 0 ? [] : [{ market, average: values.reduce((sum, value) => sum + value, 0) / values.length, games: values.length }]
  })
}
