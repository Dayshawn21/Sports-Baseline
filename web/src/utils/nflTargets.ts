import type { NflSlateLine } from '~/types/nfl'
import { formatProjection } from '~/utils/nflLabels'

export const TARGETS_REFERENCE_NOTE = 'Season-average reference. Gaps are descriptive; no betting recommendation.'
export const TARGETS_PROBABILITY_NOTE = 'P(over) is unavailable because the calibration check did not pass.'

export function isTargetsReference(market: string): boolean {
  return market === 'receiving_targets'
}

export function targetsReferenceSummary(row: Pick<NflSlateLine, 'market' | 'projection' | 'line' | 'gamesInSample'>): string {
  if (row.projection === null) {
    return row.gamesInSample === 0
      ? 'Reference unavailable: no valid pre-week targets history'
      : 'Reference unavailable: fewer than 4 valid games in the baseline season'
  }
  const line = row.line === null ? '' : ` vs ${formatProjection(row.market, row.line)} line`
  return `Season-average reference ${formatProjection(row.market, row.projection)}${line}; descriptive gap`
}
