export type NflPropPeriod = 'full_game' | 'first_half' | 'q1'

interface NflSegmentedLine {
  segment: string
}

/** Returns only the selected weekly game period, without changing source rows. */
export function filterNflSlateLinesByPeriod<T extends NflSegmentedLine>(lines: T[], period: NflPropPeriod): T[] {
  return lines.filter(line => line.segment === period)
}
