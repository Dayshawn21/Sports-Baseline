import type { NflSlateLine } from '~/types/nfl'

type SnapShare = Pick<NflSlateLine, 'snapShare' | 'snapShareGames'>

/**
 * "68% · 14 g, season-weighted" for the RB/TE anytime-TD evidence panel.
 * Null when snap share does not feed the line; never "0%" when the player has no snap history.
 */
export function snapShareLabel(row: SnapShare): string | null {
  if (row.snapShareGames === null) return null
  if (row.snapShare === null || row.snapShareGames === 0) return 'No snap history (position average used)'
  return `${Math.round(row.snapShare * 100)}% · ${row.snapShareGames} g, season-weighted`
}
