import type { NflSlateLine } from '~/types/nfl'
import { STALE_FLAG } from '~/utils/nflBaseline'
import { formatProjection } from '~/utils/nflLabels'
import { isTargetsReference, targetsReferenceSummary } from '~/utils/nflTargets'

type SignalLine = Pick<
  NflSlateLine,
  'edge' | 'gamesInSample' | 'line' | 'market' | 'opponentAdjustmentPct' | 'opponentAllowedHistory' | 'opponentTeam'
  | 'position' | 'projection' | 'qualityFlags' | 'recentForm' | 'usageAdjustmentPct'
>

export function edgeLabel(edge: number | null): string {
  return edge === null ? '--' : `${edge > 0 ? '+' : ''}${edge.toFixed(1)}`
}

/** Edge as a share of the line, the board's ranking metric made readable. */
export function edgePctLabel(value: number | null): string {
  return value === null ? '--' : `${value > 0 ? '+' : ''}${(value * 100).toFixed(1)}%`
}

/** Flags every normally priced line carries; they describe the method, not a problem. */
const ROUTINE_FLAGS = new Set(['historical_baseline', 'recent_market_model', 'opponent_adjusted', 'usage_adjusted'])

export function trustLabel(row: Pick<SignalLine, 'qualityFlags'>): string {
  if (row.qualityFlags.includes(STALE_FLAG)) return 'Review'
  if (row.qualityFlags.some(flag => !ROUTINE_FLAGS.has(flag))) return 'Watch'
  return 'Ready'
}

/**
 * What the opponent gave up to the whole position group per game. It is a team total
 * (every WR combined), so it must never read as a single player's number.
 */
export function allowedLabel(row: Pick<SignalLine, 'market' | 'opponentAllowedHistory' | 'opponentTeam' | 'position'>): string | null {
  const average = row.opponentAllowedHistory.average
  if (average === null) return null
  const team = row.opponentTeam ?? 'Opponent'
  const group = row.position ? `${row.position}s` : 'the position'
  if (row.market === 'anytime_touchdown') return `${team} allowed a TD to ${group} in ${formatProjection(row.market, average)} of games`
  return `${team} allowed ${group} ${formatProjection(row.market, average)}/g`
}

function percent(value: number): string {
  return `${Math.round(value * 100)}%`
}

/** The fitted over/under split for a line, or null where the fit is not shown. */
export function overProbabilityLabel(row: Pick<NflSlateLine, 'pOver' | 'pUnder'>): string | null {
  if (row.pOver === null || row.pUnder === null) return null
  return `Over ${percent(row.pOver)} · Under ${percent(row.pUnder)}`
}

export function overShareLabel(pOver: number | null): string | null {
  return pOver === null ? null : `${percent(pOver)} over`
}

export function signalSummary(row: SignalLine): string {
  if (isTargetsReference(row.market)) return targetsReferenceSummary(row)
  const details: string[] = []
  if (row.projection !== null && row.line !== null) details.push(`Model ${formatProjection(row.market, row.projection)} vs ${formatProjection(row.market, row.line)} line`)
  if (row.recentForm.average !== null) details.push(`Recent ${formatProjection(row.market, row.recentForm.average)} avg (${row.recentForm.values.length}g)`)
  const allowed = allowedLabel(row)
  if (allowed !== null) details.push(allowed)
  if (row.usageAdjustmentPct !== null && Math.abs(row.usageAdjustmentPct) >= 1) details.push(`Usage ${row.usageAdjustmentPct > 0 ? '+' : ''}${row.usageAdjustmentPct.toFixed(1)}%`)
  if (row.opponentAdjustmentPct !== null && Math.abs(row.opponentAdjustmentPct) >= 3) details.push(`Matchup ${row.opponentAdjustmentPct > 0 ? '+' : ''}${row.opponentAdjustmentPct.toFixed(1)}%`)
  return details.length ? details.join(' · ') : row.gamesInSample ? `${row.gamesInSample}-game model baseline` : 'Market comparison unavailable'
}
