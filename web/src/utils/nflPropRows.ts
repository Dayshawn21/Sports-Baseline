interface NflPropRowLine {
  fetchedAt: string
  line: number | null
  lineId: number
  market: string
  oddsType: string | null
  playerId: number
  segment: string
}

export interface NflPropRow<T extends NflPropRowLine> {
  alternates: T[]
  primary: T
}

function newestLine<T extends NflPropRowLine>(lines: T[]): T {
  return [...lines].sort((left, right) => right.fetchedAt.localeCompare(left.fetchedAt) || right.lineId - left.lineId)[0]
}

function lineKey(line: NflPropRowLine): string {
  return `${line.playerId}:${line.market}:${line.segment}`
}

function alternateKey(line: NflPropRowLine): string {
  return `${line.oddsType ?? 'unknown'}:${line.line ?? 'unknown'}`
}

/** Keeps the current standard line visible while preserving current alternates for evidence. */
export function groupNflPropRows<T extends NflPropRowLine>(lines: T[]): NflPropRow<T>[] {
  const groups = new Map<string, T[]>()
  for (const line of lines) {
    const key = lineKey(line)
    groups.set(key, [...(groups.get(key) ?? []), line])
  }

  return [...groups.values()].map(group => {
    const standardLines = group.filter(line => line.oddsType === 'standard')
    const primary = newestLine(standardLines.length ? standardLines : group)
    const alternates = new Map<string, T>()
    for (const line of group.filter(line => line.lineId !== primary.lineId && line.oddsType !== 'standard')) {
      const key = alternateKey(line)
      const existing = alternates.get(key)
      if (!existing || newestLine([existing, line]).lineId === line.lineId) alternates.set(key, line)
    }
    return { primary, alternates: [...alternates.values()].sort((left, right) => (left.line ?? 0) - (right.line ?? 0)) }
  })
}
