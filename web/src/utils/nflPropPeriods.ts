export type NflPropPeriod = 'full_game' | 'first_half' | 'q1'

export const NFL_PROP_PERIOD_OPTIONS: Array<{ label: string, value: NflPropPeriod }> = [
  { value: 'full_game', label: 'Full game' },
  { value: 'first_half', label: '1st half' },
  { value: 'q1', label: '1st quarter' },
]

interface NflSegmentedLine {
  segment: string
}

/** Returns only the selected weekly game period, without changing source rows. */
export function filterNflSlateLinesByPeriod<T extends NflSegmentedLine>(lines: T[], period: NflPropPeriod): T[] {
  return lines.filter(line => line.segment === period)
}
