/**
 * The one gap unit every slate and the home gaps table show: model minus line in the stat's own units, "+32.6 yds",
 * "-1.1 pts". A stat with no short unit shows the signed number alone; its market label sits beside it.
 */
export function signedGapUnits(gap: number | null, unit?: string): string {
  if (gap === null || !Number.isFinite(gap)) return '--'
  const sign = gap > 0 ? '+' : gap < 0 ? '-' : ''
  return `${sign}${Math.abs(gap).toFixed(1)}${unit ? ` ${unit}` : ''}`
}

/** The same gap sized against a line: "70% of the line"; unsigned, so it never reads as a change. */
export function gapShareOfLine(share: number | null): string | null {
  return share === null || !Number.isFinite(share) ? null : `${Math.round(Math.abs(share) * 100)}% of the line`
}
