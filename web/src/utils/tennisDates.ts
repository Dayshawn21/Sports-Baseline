import { ctDayKey } from '~/utils/format'

/**
 * The stored `match_date` values that can hold a Central-time day's matches.
 *
 * `match_date` is the UTC date, and a Central day runs from 05:00 (or 06:00)
 * UTC on that date to the same time on the next, so an evening match lands on
 * the next UTC date. Fetching only the chosen date dropped every match from
 * about 7pm Central on.
 */
export function utcDatesForCentralDay(date: string): [string, string] {
  const next = new Date(`${date}T00:00:00Z`)
  next.setUTCDate(next.getUTCDate() + 1)
  return [date, next.toISOString().slice(0, 10)]
}

/** The UTC dates a slate shows when no date is chosen: today's and the next. */
export function defaultSlateDates(now: Date): [string, string] {
  return utcDatesForCentralDay(now.toISOString().slice(0, 10))
}

function shiftDate(date: string, days: number): string {
  const shifted = new Date(`${date}T00:00:00Z`)
  shifted.setUTCDate(shifted.getUTCDate() + days)
  return shifted.toISOString().slice(0, 10)
}

/**
 * The Central day the slate opens on with no date picked: today while any of
 * today's matches is still to start, then tomorrow. Tennis runs overnight, so a
 * CT evening's remaining play is mostly on tomorrow's date.
 */
export function defaultTennisDay(startTimes: readonly (string | null)[], now: number): string {
  const today = ctDayKey(now)
  const startsLaterToday = startTimes.some((value) => {
    const start = Date.parse(value ?? '')
    return Number.isFinite(start) && start > now && ctDayKey(start) === today
  })
  return startsLaterToday ? today : shiftDate(today, 1)
}

/** The arrows' targets: the slate always shows one day, so they step one day. */
export function tennisDateNeighbors(date: string): { previous: string, next: string } {
  return { previous: shiftDate(date, -1), next: shiftDate(date, 1) }
}
