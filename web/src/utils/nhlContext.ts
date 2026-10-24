import type { NhlContextSource, NhlGameContext, NhlGoalieSide, NhlInjury } from '~/types/nhlContext'
import { nhlTimeLabel } from '~/utils/nhlGame'

export function unavailableNhlContext(awayTeam: string, homeTeam: string): NhlGameContext {
  const source = { source: 'ESPN', fetchedAt: null, sourceTimestamp: null, freshness: 'unavailable' } as const
  const side = (team: string): NhlGoalieSide => ({
    team, espnAthleteId: null, playerId: null, playerName: null, status: 'unavailable', rawStatus: null, linkReason: null,
  })
  return {
    injuries: { ...source, away: [], home: [] },
    goalies: { ...source, away: side(awayTeam), home: side(homeTeam) },
  }
}

/** Keep server availability decisions; only age a valid report further in the browser. */
export function nhlContextFreshness(report: NhlContextSource | undefined, startUtc: string | null, now: Date) {
  const fetched = Date.parse(report?.fetchedAt ?? '')
  const start = Date.parse(startUtc ?? '')
  const asOf = now.getTime()
  if (!report || report.freshness === 'unavailable' || !Number.isFinite(fetched)
    || !Number.isFinite(start) || !Number.isFinite(asOf) || fetched >= start || fetched > asOf) return 'unavailable'
  return report.freshness === 'stale' || Math.min(start, asOf) - fetched > 6 * 60 * 60 * 1000 ? 'stale' : 'fresh'
}

export function nhlContextSource(report: NhlContextSource | undefined, startUtc: string | null, now: Date) {
  const freshness = nhlContextFreshness(report, startUtc, now)
  const fetchedAt = report?.fetchedAt && Number.isFinite(Date.parse(report.fetchedAt)) ? report.fetchedAt : null
  return { freshness, label: freshness === 'fresh' ? 'Fresh' : freshness === 'stale' ? 'Stale' : 'Unavailable',
    fetchedAt, fetchedLabel: fetchedAt ? nhlTimeLabel(fetchedAt, true) : 'Fetch time unavailable' }
}

export function nhlGoalieLabel(side: NhlGoalieSide, available: boolean) {
  if (!available || side.status === 'unavailable') return { name: null, status: 'Unavailable', unresolved: false }
  if (side.status === 'not_reported') return { name: null, status: 'Not reported', unresolved: false }
  const status = side.status === 'expected' ? 'Expected' : side.status === 'confirmed' ? 'Confirmed'
    : `Unknown status${side.rawStatus ? `: ${side.rawStatus}` : ''}`
  return { name: side.playerName, status, unresolved: side.playerName !== null && side.playerId === null }
}

export function nhlSlateContext(context: NhlGameContext | undefined, away: string, home: string, startUtc: string | null, now: Date) {
  const report = context ?? unavailableNhlContext(away, home)
  const injuries = nhlContextSource(report.injuries, startUtc, now)
  const goalies = nhlContextSource(report.goalies, startUtc, now)
  const available = injuries.freshness !== 'unavailable'
  return {
    injuries: { ...injuries, away: available ? report.injuries.away.length : null,
      home: available ? report.injuries.home.length : null,
      empty: available && report.injuries.away.length + report.injuries.home.length === 0 },
    goalies: { ...goalies, away: nhlGoalieLabel(report.goalies.away, goalies.freshness !== 'unavailable'),
      home: nhlGoalieLabel(report.goalies.home, goalies.freshness !== 'unavailable') },
  }
}

export function nhlContextTime(value: string | null) {
  return value !== null && Number.isFinite(Date.parse(value)) ? { dateTime: value, label: nhlTimeLabel(value, true) } : null
}

export function nhlInjuryDetails(injury: NhlInjury) {
  return { ...injury, updated: nhlContextTime(injury.sourceUpdatedAt),
    identity: injury.teamMismatch ? 'Unresolved identity / Source team differs from roster'
      : injury.playerId === null ? 'Unresolved identity' : null }
}
