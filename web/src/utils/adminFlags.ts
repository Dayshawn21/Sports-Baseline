// Mirrors MIN_MATCHES in api/app/ingest/player_stats.py, below which no surface row is written.
const MIN_SURFACE_MATCHES = 3

/** Why a player with an ml_features_partial flag may not be fixable by re-fetching. */
export function surfaceGapNote(missingSurfaces: string[]): string | null {
  if (missingSurfaces.length === 0) return null
  return `No ${missingSurfaces.join(' or ')} stats. Fix Stats can add them only with ${MIN_SURFACE_MATCHES}+ matches on that surface in the last 52 weeks.`
}
