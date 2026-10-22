import type { MatchResearch, MatchResearchStats, MatchWorkload } from '~/types/tennis'

interface ResearchMatch {
  p1: { playerId: number }
  p2: { playerId: number }
  surface: string | null
  research?: MatchResearch | null
}

export function researchPair(detail: ResearchMatch, overall: boolean): [MatchResearchStats | null, MatchResearchStats | null] {
  const select = (playerId: number) => {
    const context = detail.research?.players.find(item => item.playerId === playerId)
    const stats = overall ? context?.overallStats : context?.surfaceStats
    if (!stats || stats.statPeriod !== 'last_52w') return null
    if (overall) return stats.surface == null ? stats : null
    return detail.surface && stats.surface?.toLowerCase() === detail.surface.toLowerCase() ? stats : null
  }
  return [select(detail.p1.playerId), select(detail.p2.playerId)]
}

export function researchDate(value: string | null | undefined): string {
  if (!value || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return 'Unavailable'
  const date = new Date(`${value}T12:00:00Z`)
  if (!Number.isFinite(date.getTime()) || date.toISOString().slice(0, 10) !== value) return 'Unavailable'
  return new Intl.DateTimeFormat('en-US', { year: 'numeric', month: 'short', day: 'numeric', timeZone: 'UTC' }).format(date)
}

export function researchTimestamp(value: string | null | undefined): string {
  if (!value || !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}/.test(value) ||
    !/(?:Z|[+-]\d{2}:\d{2})$/i.test(value) || researchDate(value.slice(0, 10)) === 'Unavailable') return 'Unavailable'
  const date = new Date(value)
  if (!Number.isFinite(date.getTime())) return 'Unavailable'
  return new Intl.DateTimeFormat('en-US', {
    year: 'numeric', month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit',
    hour12: true, timeZone: 'America/Chicago',
  }).format(date) + ' CT'
}

export function workloadSets(value: MatchWorkload | null | undefined): string {
  if (!value) return 'Unavailable'
  if (value.matchesWithCompleteScores < value.matchesPlayed) {
    return value.completedSets > 0 ? `At least ${value.completedSets}` : 'Unavailable'
  }
  return String(value.completedSets)
}
