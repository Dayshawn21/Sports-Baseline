interface SortableBoardRow {
  game: { gameId: number, startUtc: string | null }
  row: { playerName: string, playerId: number }
}

/** Start time in ms; a missing or unreadable start sorts last. */
export function boardStartTime(startUtc: string | null): number {
  const time = startUtc === null ? NaN : Date.parse(startUtc)
  return Number.isNaN(time) ? Infinity : time
}

/** Start time, then player name; game and player ids keep the order stable when names tie. */
export function compareBoardRows(left: SortableBoardRow, right: SortableBoardRow): number {
  const leftStart = boardStartTime(left.game.startUtc)
  const rightStart = boardStartTime(right.game.startUtc)
  if (leftStart !== rightStart) return leftStart < rightStart ? -1 : 1
  return left.row.playerName.localeCompare(right.row.playerName)
    || left.game.gameId - right.game.gameId
    || left.row.playerId - right.row.playerId
}

export function propBoardPath(sport: 'nba' | 'nhl', date: string | null, market: string): string | null {
  if (date === null) return null
  return `/${sport}/props?${new URLSearchParams({ date, market })}`
}
