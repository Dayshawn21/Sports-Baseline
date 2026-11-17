import type { FetchEloRequest, FetchStatsRequest, SetEloRequest } from '~/types/admin'

// Mirrors MIN_MATCHES in api/app/ingest/player_stats.py, below which no surface row is written.
const MIN_SURFACE_MATCHES = 3

/** Why a player with an ml_features_partial flag may not be fixable by re-fetching. */
export function surfaceGapNote(missingSurfaces: string[]): string | null {
  if (missingSurfaces.length === 0) return null
  return `No ${missingSurfaces.join(' or ')} stats. Fix Stats can add them only with ${MIN_SURFACE_MATCHES}+ matches on that surface in the last 52 weeks.`
}

/** Set ELO's four inputs as typed; an empty string is an unset field. */
export interface SetEloInputs {
  elo: string
  hard: string
  clay: string
  grass: string
}

export const EMPTY_ELO_INPUTS: SetEloInputs = { elo: '', hard: '', clay: '', grass: '' }

/** Null until Overall holds a nonzero number; a blank surface is sent as null. */
export function buildSetEloPayload(inputs: SetEloInputs): SetEloRequest | null {
  const elo = Number(inputs.elo)
  if (!elo) return null
  return {
    elo,
    eloHard: inputs.hard ? Number(inputs.hard) : null,
    eloClay: inputs.clay ? Number(inputs.clay) : null,
    eloGrass: inputs.grass ? Number(inputs.grass) : null,
  }
}

/** An empty slug lets the API fall back to the saved or auto-generated one. */
export function fixStatsPayload(slug: string): FetchStatsRequest {
  return { taSlug: slug || null }
}

/** The name goes as an override only when it differs from ours. */
export function fetchEloPayload(name: string, playerName: string): FetchEloRequest {
  return { taName: name !== playerName ? name : null }
}

export function hasEloFlag(flags: readonly string[]): boolean {
  return flags.some(flag => flag === 'elo_missing' || flag === 'p1_elo_missing' || flag === 'p2_elo_missing')
}

export function hasStatsFlag(flags: readonly string[]): boolean {
  return flags.includes('ml_features_partial')
}
