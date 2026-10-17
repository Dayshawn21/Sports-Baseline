export type NflPositionFilter = 'all' | 'QB' | 'RB' | 'WR' | 'TE' | 'K'

export const NFL_POSITION_OPTIONS: Array<{ label: string, value: NflPositionFilter }> = [
  { value: 'all', label: 'All' },
  { value: 'QB', label: 'QB' },
  { value: 'RB', label: 'RB' },
  { value: 'WR', label: 'WR' },
  { value: 'TE', label: 'TE' },
  { value: 'K', label: 'K' },
]

interface NflPositionedLine {
  position: string | null
}

export function filterNflSlateLinesByPosition<T extends NflPositionedLine>(lines: T[], position: NflPositionFilter): T[] {
  return position === 'all' ? lines : lines.filter(line => line.position === position)
}

export function groupNflSlateLinesByPosition<T extends NflPositionedLine>(lines: T[]): Array<{ position: string, lines: T[] }> {
  const groups = NFL_POSITION_OPTIONS.slice(1).map(position => ({
    position: position.value,
    lines: lines.filter(line => line.position === position.value),
  })).filter(group => group.lines.length)
  const otherLines = lines.filter(line => !NFL_POSITION_OPTIONS.some(option => option.value === line.position))
  return otherLines.length ? [...groups, { position: 'Other', lines: otherLines }] : groups
}
