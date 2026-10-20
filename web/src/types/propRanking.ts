import type { TrackSignal } from '~/types/tennis'

/** One payout slice of the forward ranking check (27i's rule), the same for every sport. */
export interface PropRankingSlice {
  oddsType: 'standard' | 'goblin' | 'demon'
  side: 'over' | 'under'
  verdict: 'insufficient' | 'adopt' | 'reject'
  n: number
  weeks: number
  hits: number
  hitRate: number | null
  standardError: number | null
  breakEven: number
  signal: TrackSignal
}

/** `/nfl/model/ranking` and `/nba/model/ranking` (20g4); a sport's adoption item reads its slice verdicts here. */
export interface PropRankingRecord<P extends string | null = string> {
  gradedAt: string
  season: number
  modelVersion: string
  overProbabilityVersion: P
  rule: { minPicks: number, minWeeks: number, minPickMargin: number }
  finishedWeeks: number[]
  lastSettledWeek: number | null
  frozenRows: number
  excluded: Record<string, number>
  coverage: { week: number, lines: number, frozen: number }[]
  funnel: { calls: number, withPOver: number, picks: number, bets: number }
  slices: PropRankingSlice[]
}
