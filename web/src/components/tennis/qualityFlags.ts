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

export function getDisplayFlagLabel(flag: string): string {
  return flag === 'partial_context' ? 'Partial context' : flag
}
