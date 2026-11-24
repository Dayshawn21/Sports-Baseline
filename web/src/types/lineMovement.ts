/** Stored, pre-start lines from one book per market. */
export interface LineMovementHistory {
  market: 'spread' | 'total'
  book: string
  steps: { fetchedAt: string, line: number }[]
}

export interface LineMovementGame {
  homeTeam: string
  awayTeam: string
  startUtc: string | null
  lineHistory: LineMovementHistory[]
}
