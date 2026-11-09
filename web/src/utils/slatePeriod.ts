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

/** The slate's newest fetch while its odds are stale, which every row's own age is compared against; else null. */
export function staleOddsSince(latestOddsMs: number | null, startsMs: readonly number[], now: number): number | null {
  return latestOddsMs !== null && isOddsStale(latestOddsMs, startsMs, now) ? latestOddsMs : null
}

/** A count part of the period line: "1 game", "15 games", "33 matches". */
export function countPart(count: number, singular: string, plural = `${singular}s`): string {
  return `${count} ${count === 1 ? singular : plural}`
}

/** A slate table's count: "7 games", or "1 of 7 games" while a search filters it. */
export function tableCountPart(shown: number, total: number, searching: boolean, singular: string, plural = `${singular}s`): string {
  const all = countPart(total, singular, plural)
  return searching ? `${shown} of ${all}` : all
}

/** Note tags that fit one phone line, and the rest, which a "+N" stands in for. */
export function splitTags<T>(tags: readonly T[], limit: number): { shown: T[], hidden: T[] } {
  const cut = Math.max(0, limit)
  return { shown: tags.slice(0, cut), hidden: tags.slice(cut) }
}

/** Parseable start times, for the stale-odds check. */
export function startTimes(starts: readonly (string | null | undefined)[]): number[] {
  return starts.flatMap(start => {
    const time = start ? Date.parse(start) : Number.NaN
    return Number.isNaN(time) ? [] : [time]
  })
}

const HOUR_MS = 60 * 60 * 1000
const DAY_MS = 24 * HOUR_MS

/** How old a stale fetch is, to the nearest unit, so Tuesday afternoon reads "6 days old" on Monday morning. */
export function oddsAgeLabel(fetchedMs: number, now: number): string {
  const hours = Math.round(Math.max(0, now - fetchedMs) / HOUR_MS)
  if (hours < 24) return `${countPart(hours, 'hour')} old`
  return `${countPart(Math.round(hours / 24), 'day')} old`
}

/** The odds part of the period line, or null when no odds are stored; `staleAge` is set only while the odds are stale. */
export function oddsPart(label: string | null, staleAge: string | null): string | null {
  if (!label) return null
  return `odds ${label}${staleAge ? ` · ${staleAge}` : ''}`
}

export interface SlateCounts {
  games: number
  finals: number
  oddsUpdated: string | null
  oddsUpdatedMs: number | null
}

/** A game slate's period line: "Week 9 · 15 games · 1 final · odds Tue 3:12 PM CT · 6 days old". An empty slate shows the period alone. */
export function gameSlateLine(period: string, counts: SlateCounts, startsMs: readonly number[], now: number): string {
  if (counts.games === 0) return period
  const staleSince = staleOddsSince(counts.oddsUpdatedMs, startsMs, now)
  return slatePeriodLine([
    period,
    countPart(counts.games, 'game'),
    counts.finals > 0 && countPart(counts.finals, 'final', 'final'),
    oddsPart(counts.oddsUpdated, staleSince === null ? null : oddsAgeLabel(staleSince, now)),
  ])
}

const CENTRAL = 'America/Chicago'
const AGE_DAY = new Intl.DateTimeFormat('en-CA', { timeZone: CENTRAL, year: 'numeric', month: '2-digit', day: '2-digit' })
const AGE_CLOCK = new Intl.DateTimeFormat('en-US', { timeZone: CENTRAL, hour: 'numeric', minute: '2-digit' })
const AGE_WEEKDAY = new Intl.DateTimeFormat('en-US', { timeZone: CENTRAL, weekday: 'short' })
const AGE_DATE = new Intl.DateTimeFormat('en-US', { timeZone: CENTRAL, month: 'short', day: 'numeric' })
// Under six days a weekday names one day only; past that it could mean two.
const WEEKDAY_SPAN_MS = 6 * 24 * 60 * 60 * 1000

/** The newest parseable time, as epoch milliseconds; null when none parse. */
export function latestTime(times: readonly (string | null | undefined)[]): number | null {
  const parsed = startTimes(times)
  return parsed.length ? Math.max(...parsed) : null
}

/**
 * A row's odds age, shown only while the slate's odds are stale: "as of 9:05 AM" the same Central day, "as of Tue"
 * within six days, else "as of Oct 27". A row with prices but no stored fetch time says so rather than guessing.
 */
export function oddsAsOf(fetchedMs: number | null, now: number): string {
  if (fetchedMs === null || !Number.isFinite(fetchedMs)) return 'odds time not stored'
  if (AGE_DAY.format(fetchedMs) === AGE_DAY.format(now)) return `as of ${AGE_CLOCK.format(fetchedMs)}`
  return `as of ${now - fetchedMs < WEEKDAY_SPAN_MS ? AGE_WEEKDAY.format(fetchedMs) : AGE_DATE.format(fetchedMs)}`
}

const DAY_CLOCK = new Intl.DateTimeFormat('en-US', { timeZone: CENTRAL, weekday: 'short', hour: 'numeric', minute: '2-digit' })

/** A start time as the slates write it: "Mon 7:15 PM CT". */
export function dayClockCt(ms: number): string {
  return `${DAY_CLOCK.format(ms).replace(',', '')} CT`
}

// A slate's prices come from one ingest run, which takes minutes; rows within this of its newest fetch share the head's age.
const SAME_RUN_MS = HOUR_MS

/**
 * A stale row's own odds age, shown only when it differs from the slate's newest fetch, which the head already names.
 * A row with prices but no stored fetch time says so rather than guessing.
 */
export function rowOddsAge(rowFetchedMs: number | null, slateFetchedMs: number, now: number): string | null {
  if (rowFetchedMs !== null && Number.isFinite(rowFetchedMs) && Math.abs(slateFetchedMs - rowFetchedMs) <= SAME_RUN_MS) return null
  return oddsAsOf(rowFetchedMs, now)
}
