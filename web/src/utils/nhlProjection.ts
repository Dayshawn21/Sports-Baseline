import type { NhlProjection, NhlProjectionFlag } from '~/types/nhl'

export const NHL_PROJECTION_CAPTION = 'Reference projection: 20-game average, not a pick'

const FLAG_TEXT: Record<NhlProjectionFlag, string> = {
  few_prior_games: 'Too few games',
  low_toi: 'Under 12 min a game',
  not_center: 'Centers only',
  no_goalie_report: 'No starter report',
  starter_unconfirmed: 'Starter not confirmed',
  other_starter_expected: 'Another goalie expected',
  context_stale: 'Starter report is stale',
  injured_out: 'Injured: out',
  injury_listed: 'Injury listed',
  injury_context_stale: 'Injury report is stale',
}

export function nhlProjectionValue(projection: NhlProjection): string {
  return projection.value === null ? '-' : projection.value.toFixed(1)
}

/** The gap to a line, signed, in the market's unit; a dash when no number is shown. */
export function nhlGapLabel(gap: number | null): string {
  if (gap === null) return '-'
  const text = Math.abs(gap).toFixed(1)
  if (Number(text) === 0) return text
  return `${gap > 0 ? '+' : '-'}${text}`
}

/** Why a number is missing, or what to qualify one that is shown; null when there is nothing to say. */
export function nhlProjectionNote(projection: NhlProjection): string | null {
  if (projection.flags.length === 0) return null
  return projection.flags.map(flag => FLAG_TEXT[flag]).join(' · ')
}
