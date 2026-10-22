import type { NflAllowedMetric, NflContextMetric, NflContextPlayer, NflPositionAllowed } from '~/types/nfl'

export const POSITION_ALLOWED_ROWS: { key: keyof NflPositionAllowed, label: string }[] = [
  { key: 'rbCarries', label: 'RB carries' },
  { key: 'rbRushYards', label: 'RB rush yards' },
  { key: 'rbReceptions', label: 'RB receptions' },
  { key: 'rbRecYards', label: 'RB rec yards' },
  { key: 'wrReceptions', label: 'WR receptions' },
  { key: 'wrRecYards', label: 'WR rec yards' },
  { key: 'teReceptions', label: 'TE receptions' },
  { key: 'teRecYards', label: 'TE rec yards' },
]

export function contextValue(metric: NflContextMetric, share = false): string {
  if (metric.value === null) return '-'
  return share ? `${(metric.value * 100).toFixed(1)}%` : metric.value.toFixed(1)
}

export function contextCoverage(metric: NflContextMetric): string {
  if (metric.eligibleGames === 0) return '0 eligible games'
  return `${metric.observedGames} / ${metric.eligibleGames} games (${Math.round(metric.observedGames / metric.eligibleGames * 100)}%)`
}

export function contextRank(metric: NflAllowedMetric): string {
  return metric.rank === null ? 'Unranked' : `Rank ${metric.rank} / ${metric.rankedTeams}`
}

const DATE_FORMAT = new Intl.DateTimeFormat('en-US', { month: 'short', day: 'numeric', timeZone: 'UTC' })

function gameDate(value: string | null): string | null {
  if (value === null || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return null
  const date = new Date(`${value}T00:00:00Z`)
  if (Number.isNaN(date.getTime()) || date.toISOString().slice(0, 10) !== value) return null
  return DATE_FORMAT.format(date)
}

export function contextDates(metric: NflContextMetric): string | null {
  const start = gameDate(metric.windowStart)
  const end = gameDate(metric.windowEnd)
  if (start === null || end === null) return null
  return metric.windowStart === metric.windowEnd ? start : `${start} - ${end}`
}

export function contextUnavailable(metric: NflContextMetric): string | null {
  if (metric.value !== null) return null
  switch (metric.reason) {
    case 'no_history': return 'No pre-week games'
    case 'missing_data': return 'Metric not loaded'
    case 'zero_denominator': return 'Team total is zero'
    case 'unknown_kickoff': return 'Kickoff time unavailable'
    default: return 'Unavailable'
  }
}

export function orderedContextPlayers(players: NflContextPlayer[]): NflContextPlayer[] {
  const compare = (first: string, second: string) => first < second ? -1 : first > second ? 1 : 0
  return [...players].sort((a, b) => compare(a.team, b.team) || compare(a.name, b.name) || a.playerId - b.playerId)
}
