// Types for the Admin Data Quality section.
// Field names are camelCase — FastAPI backend uses alias_generator=to_camel.

export interface AdminSession {
  keyRequired: boolean
}

export interface FlaggedPlayer {
  playerId: number
  playerName: string
  tour: string
  flags: string[]
  hasElo: boolean
  hasStats: boolean
  taSlug: string | null   // current DB slug override (null if not set)
  autoSlug: string        // computed slug from player name — used for UI prefill
}

export interface FlaggedPlayersResponse {
  count: number
  players: FlaggedPlayer[]
}

export interface FetchStatsRequest {
  taSlug?: string | null
}

export interface FetchStatsResponse {
  success: boolean
  playerName: string
  matchesFound: number
  error: string | null
}

export interface FetchEloRequest {
  taName?: string | null  // TennisAbstract name override
}

export interface FetchEloResponse {
  success: boolean
  playerName: string
  elo: number | null
  error: string | null
}

export interface SetEloRequest {
  elo: number
  eloHard?: number | null
  eloClay?: number | null
  eloGrass?: number | null
}

export interface SetEloResponse {
  success: boolean
  playerId: number
  playerName: string
}
