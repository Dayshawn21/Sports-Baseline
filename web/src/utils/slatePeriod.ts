/** A proposed default, confirmed at the 57a spec review: odds older than this read as stale while games remain. */
export const STALE_ODDS_MS = 6 * 60 * 60 * 1000

/** The page head's period line: the parts that have a value, joined with a middle dot. */
export function slatePeriodLine(parts: readonly (string | null | undefined | false)[]): string {
  return parts.filter((part): part is string => typeof part === 'string' && part.trim().length > 0).join(' · ')
}

/** True when the newest odds fetch is over six hours old and at least one game has not started. */
export function isOddsStale(latestOddsMs: number | null, startsMs: readonly number[], now: number): boolean {
  if (latestOddsMs === null || !Number.isFinite(latestOddsMs)) return false
  if (now - latestOddsMs <= STALE_ODDS_MS) return false
  return startsMs.some(start => start > now)
}

/** A count part of the period line: "1 game", "15 games", "33 matches". */
export function countPart(count: number, singular: string, plural = `${singular}s`): string {
  return `${count} ${count === 1 ? singular : plural}`
}

/** Parseable start times, for the stale-odds check. */
export function startTimes(starts: readonly (string | null | undefined)[]): number[] {
  return starts.flatMap(start => {
    const time = start ? Date.parse(start) : Number.NaN
    return Number.isNaN(time) ? [] : [time]
  })
}

/** The odds part of the period line, or null when no odds are stored. */
export function oddsPart(label: string | null, stale: boolean): string | null {
  if (!label) return null
  return `odds ${label}${stale ? ' (stale)' : ''}`
}

export interface SlateCounts {
  games: number
  finals: number
  oddsUpdated: string | null
  oddsUpdatedMs: number | null
}

/** A game slate's period line: "Week 9 · 15 games · 1 final · odds Tue 3:12 PM CT". An empty slate shows the period alone. */
export function gameSlateLine(period: string, counts: SlateCounts, startsMs: readonly number[], now: number): string {
  if (counts.games === 0) return period
  return slatePeriodLine([
    period,
    countPart(counts.games, 'game'),
    countPart(counts.finals, 'final', 'final'),
    oddsPart(counts.oddsUpdated, isOddsStale(counts.oddsUpdatedMs, startsMs, now)),
  ])
}
