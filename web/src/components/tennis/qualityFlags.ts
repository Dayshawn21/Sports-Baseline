import type { MatchPrediction } from '~/types/tennis'

function normalizeName(name: string): string {
  return name.trim().toLowerCase()
}

export function getQualityFlagLabel(match: MatchPrediction, flag: string): string {
  if (flag !== 'ml_features_partial') return flag

  const p1 = normalizeName(match.p1Name)
  const p2 = normalizeName(match.p2Name)
  const surface = (match.surface ?? '').trim().toLowerCase()
  const isSheltonZhang =
    (p1 === 'ben shelton' && p2 === 'zhizhen zhang') ||
    (p1 === 'zhizhen zhang' && p2 === 'ben shelton')

  if (isSheltonZhang && surface === 'clay') {
    return 'Missing clay stats for Zhizhen Zhang'
  }

  return flag
}

const RECENT_FORM_MISSING_FLAG = 'ctx_last90_missing'

// Most players outside the top 50 lack 3 matches against top-20 or top-50
// opponents, so these fire on nearly every match and are never shown.
const HIDDEN_CONTEXT_FLAGS = new Set(['ctx_top20_missing', 'ctx_top50_missing'])

/** Show "partial context" only for missing recent form; drop the opponent-rank gaps. */
export function getDisplayFlags(flags: string[]): string[] {
  const otherFlags = flags.filter(
    (flag) => flag !== RECENT_FORM_MISSING_FLAG && !HIDDEN_CONTEXT_FLAGS.has(flag),
  )
  return flags.includes(RECENT_FORM_MISSING_FLAG) ? ['partial_context', ...otherFlags] : otherFlags
}

export function getDisplayFlagLabel(match: MatchPrediction, flag: string): string {
  if (flag === 'partial_context') return 'Partial context'
  return getQualityFlagLabel(match, flag)
}
