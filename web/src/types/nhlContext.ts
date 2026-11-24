export type NhlContextFreshness = 'fresh' | 'stale' | 'unavailable'
export type NhlPlayerLinkReason = 'matched' | 'no_candidate' | 'ambiguous' | 'team_mismatch' | 'missing_team' | 'position_mismatch' | 'not_reported'

export interface NhlContextSource {
  source: 'ESPN'
  fetchedAt: string | null
  sourceTimestamp: string | null
  freshness: NhlContextFreshness
}

export interface NhlInjury {
  espnAthleteId: string
  playerId: number | null
  playerName: string
  team: string
  status: string
  detail: string | null
  sourceUpdatedAt: string | null
  returnDate: string | null
  linkReason: NhlPlayerLinkReason
  teamMismatch: boolean
}

export interface NhlGoalieSide {
  team: string
  espnAthleteId: string | null
  playerId: number | null
  playerName: string | null
  status: 'expected' | 'confirmed' | 'unknown' | 'not_reported' | 'unavailable'
  rawStatus: string | null
  linkReason: NhlPlayerLinkReason | null
}

export interface NhlInjuryContext extends NhlContextSource {
  away: NhlInjury[]
  home: NhlInjury[]
}

export interface NhlGoalieContext extends NhlContextSource {
  away: NhlGoalieSide
  home: NhlGoalieSide
}

export interface NhlGameContext {
  injuries: NhlInjuryContext
  goalies: NhlGoalieContext
}
