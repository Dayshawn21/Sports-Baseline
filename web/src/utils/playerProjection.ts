/** The projection block at the top of a player's market panel, shared by every sport. */
export interface PlayerProjectionHero {
  label: string
  /** The projected number as shown; null when there is none, and `reason` then says why. */
  value: string | null
  /** "-7.7 vs 237.5 line" against the main line; null when there is no number or no line. */
  delta: string | null
  reason: string | null
  facts: { label: string, value: string }[]
}

interface HeroLine { line: string, gap: string | null, oddsType: string | null }

/** The standard rung when one is posted, else the first; the delta reads against it. */
export function mainLine<T extends { oddsType: string | null }>(lines: readonly T[]): T | null {
  return lines.find(line => line.oddsType === null || line.oddsType === 'standard') ?? lines[0] ?? null
}

export function heroDelta(value: string | null, line: HeroLine | null): string | null {
  if (value === null || line === null || line.gap === null) return null
  const kind = line.oddsType === null || line.oddsType === 'standard' ? '' : ` ${line.oddsType}`
  return `${line.gap} vs ${line.line}${kind} line`
}

/** One stat chip in a player page head. */
export interface PlayerHeadChip { value: string, label: string }
