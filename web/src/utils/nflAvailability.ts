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

/** "WR2 (was WR1)" against the player's previous chart; null when not listed this week. */
export function depthLabel(row: DepthListing): string | null {
  if (row.depthPosition === null || row.depthRank === null) return null
  const current = `${row.depthPosition}${row.depthRank}`
  if (row.previousDepthPosition === null || row.previousDepthRank === null) return `${current} (first listing)`
  const previous = `${row.previousDepthPosition}${row.previousDepthRank}`
  return previous === current ? current : `${current} (was ${previous})`
}
