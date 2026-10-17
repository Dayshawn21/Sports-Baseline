/** A translucent version of any CSS color, including `var(--token)`, which hex alpha suffixes cannot tint. */
export function withAlpha(color: string, alpha: number): string {
  const pct = Math.round(Math.min(Math.max(alpha, 0), 1) * 100)
  return `color-mix(in srgb, ${color} ${pct}%, transparent)`
}
