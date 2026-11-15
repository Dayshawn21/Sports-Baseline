export interface InjuryTag {
  label: string
  color: string
}

/** Structural, so a slate line and a game-notes entry both fit. */
interface InjuryReport {
  injuryStatus: string | null
  practiceStatus: string | null
  injury: string | null
}

interface DepthListing {
  depthPosition: string | null
  depthRank: number | null
  previousDepthPosition: string | null
  previousDepthRank: number | null
}

const INJURY_TAGS: Record<string, InjuryTag> = {
  Out: { label: 'OUT', color: 'red' },
  Doubtful: { label: 'D', color: 'volcano' },
  Questionable: { label: 'Q', color: 'gold' },
}

const PRACTICE_LABELS: Record<string, string> = {
  'Full Participation in Practice': 'full practice',
  'Limited Participation in Practice': 'limited practice',
  'Did Not Participate In Practice': 'did not practice',
}

/** A compact game-status tag, or null when the player has no game status this week. */
export function injuryTag(status: string | null): InjuryTag | null {
  return status ? INJURY_TAGS[status] ?? null : null
}

/** "Questionable · Hamstring · limited practice"; null when the player is not on the report. */
export function injuryLabel(row: InjuryReport): string | null {
  const practice = row.practiceStatus ? PRACTICE_LABELS[row.practiceStatus] ?? row.practiceStatus : null
  const parts = [row.injuryStatus ?? (practice ? 'Practice report only' : null), row.injury, practice]
    .filter((part): part is string => Boolean(part))
  return parts.length ? parts.join(' · ') : null
}

interface ActiveDepth {
  depthPosition: string | null
  depthRank: number | null
  /** Absent in slates stored before it; null when the player is out. */
  activeDepthRank?: number | null
  outAhead?: string[]
}

const NAME_SUFFIXES = new Set(['Jr.', 'Sr.', 'II', 'III', 'IV', 'V'])

function surname(name: string): string {
  const parts = name.split(' ').filter(part => !NAME_SUFFIXES.has(part))
  return parts[parts.length - 1] ?? name
}

/** True when an Out teammate ahead (or the player's own Out) changes what the chart says. */
export function depthShifted(row: ActiveDepth): boolean {
  return row.depthRank !== null && row.activeDepthRank !== undefined && row.activeDepthRank !== row.depthRank
}

/** "RB1 (RB2 on chart, Walker out)", "RB1 on chart, out", or the plain chart rank. */
export function activeDepthLabel(row: ActiveDepth): string | null {
  if (row.depthPosition === null || row.depthRank === null) return null
  const chart = `${row.depthPosition}${row.depthRank}`
  if (!depthShifted(row)) return chart
  if (row.activeDepthRank === null || row.activeDepthRank === undefined) return `${chart} on chart, out`
  const out = (row.outAhead ?? []).map(surname).join(', ')
  return `${row.depthPosition}${row.activeDepthRank} (${chart} on chart${out ? `, ${out} out` : ''})`
}

/** The active label when an Out changes the depth, otherwise the week-over-week chart label. */
export function availabilityDepthLabel(row: ActiveDepth & DepthListing): string | null {
  return depthShifted(row) ? activeDepthLabel(row) : depthLabel(row)
}

/** "WR2 (was WR1)" against the player's previous chart; null when not listed this week. */
export function depthLabel(row: DepthListing): string | null {
  if (row.depthPosition === null || row.depthRank === null) return null
  const current = `${row.depthPosition}${row.depthRank}`
  if (row.previousDepthPosition === null || row.previousDepthRank === null) return `${current} (first listing)`
  const previous = `${row.previousDepthPosition}${row.previousDepthRank}`
  return previous === current ? current : `${current} (was ${previous})`
}
