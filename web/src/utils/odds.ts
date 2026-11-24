/** Convert American odds to an implied probability (0-1). */
export function americanToProb(american: number): number {
  if (american >= 0) return 100 / (american + 100)
  return -american / (-american + 100)
}

/** p1's no-vig probability from a two-way price, normalized as the API's devig_two_way does. */
export function devigP1(p1Odds: number | null, p2Odds: number | null): number | null {
  if (p1Odds == null || p2Odds == null) return null
  const p1 = americanToProb(p1Odds)
  const total = p1 + americanToProb(p2Odds)
  return total > 0 ? p1 / total : null
}

/** Format a probability as a percentage string, e.g. 0.654 → "65.4%" */
export function fmtPct(prob: number | null | undefined, decimals = 1): string {
  if (prob == null) return '—'
  return `${(prob * 100).toFixed(decimals)}%`
}

/** Format American odds with sign, e.g. 150 → "+150", -110 → "-110" */
export function fmtAmerican(odds: number | null | undefined): string {
  if (odds == null) return '—'
  return odds > 0 ? `+${odds}` : `${odds}`
}
