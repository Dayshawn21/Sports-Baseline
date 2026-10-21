import type { NbaInjuryReport } from '~/types/nba'

export const UNAVAILABLE_NBA_INJURIES: NbaInjuryReport = {
  source: 'ESPN', fetchedAt: null, freshness: 'unavailable', injuries: [],
}

export function nbaInjuryFreshness(
  report: NbaInjuryReport | undefined, startUtc: string | null, now: Date,
): NbaInjuryReport['freshness'] {
  const fetched = report?.fetchedAt ? Date.parse(report.fetchedAt) : NaN
  const tip = startUtc ? Date.parse(startUtc) : NaN
  const time = now.getTime()
  if (!report || report.freshness === 'unavailable' || ![fetched, tip, time].every(Number.isFinite)
    || fetched >= tip || fetched > time) return 'unavailable'
  return report.freshness === 'stale' || Math.min(tip, time) - fetched > 6 * 60 * 60 * 1000 ? 'stale' : 'fresh'
}

const INJURY_TIME = new Intl.DateTimeFormat('en-US', {
  timeZone: 'America/Chicago', year: 'numeric', month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit',
})

export function nbaInjuryTime(value: string | null): string {
  const time = value ? Date.parse(value) : NaN
  return Number.isFinite(time) ? `${INJURY_TIME.format(time)} CT` : 'Time unavailable'
}
