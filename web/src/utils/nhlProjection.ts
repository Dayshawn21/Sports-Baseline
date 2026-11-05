import type { NhlLineOnlyMarket, NhlProjection, NhlProjectionFlag } from '~/types/nhl'

export const NHL_PROJECTION_CAPTION = 'Reference projection: 20-game average, not a pick'
export const NHL_PROBABILITY_CAPTION = 'P(over): model estimate for that line, not a pick'

// These flags belong to one line, not to a market's projection, so the projection note leaves them out.
const LINE_FLAGS: ReadonlySet<NhlProjectionFlag> = new Set<NhlProjectionFlag>(['integer_line', 'no_over_probability'])

const WEAK_PROBABILITY_MARKETS: ReadonlySet<NhlLineOnlyMarket> = new Set(['time_on_ice', 'goals_allowed'])

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
  integer_line: 'Whole-number line: no P(over)',
  no_over_probability: 'No P(over) for this line',
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
  const flags = projection.flags.filter(flag => !LINE_FLAGS.has(flag))
  return flags.length === 0 ? null : flags.map(flag => FLAG_TEXT[flag]).join(' · ')
}

/** Why one line has no P(over); null when it has one or its market shows none. */
export function nhlLineProbabilityNote(flags: readonly NhlProjectionFlag[]): string | null {
  const lineFlags = flags.filter(flag => LINE_FLAGS.has(flag))
  return lineFlags.length === 0 ? null : lineFlags.map(flag => FLAG_TEXT[flag]).join(' · ')
}

/** A whole percent; under 1% and over 99% are shown as such so a rare result never reads as certain. */
export function nhlPercentLabel(probability: number | null): string {
  if (probability === null) return '--'
  const percent = Math.round(probability * 100)
  if (percent <= 0) return '<1%'
  if (percent >= 100) return '>99%'
  return `${percent}%`
}

/** Whether a market's fit covers this line: it has a probability or says why it has none. Hidden markets do neither. */
export function nhlCoversProbability(projection: NhlProjection): boolean {
  return projection.pOver !== null || projection.flags.includes('integer_line') || projection.flags.includes('no_over_probability')
}

/** The caveat for a shown market whose estimate only tied a plain normal estimate on 2025-26; null for the others. */
export function nhlProbabilityNote(market: NhlLineOnlyMarket): string | null {
  return WEAK_PROBABILITY_MARKETS.has(market) ? 'On 2025-26 this estimate was no better than a plain normal estimate.' : null
}
