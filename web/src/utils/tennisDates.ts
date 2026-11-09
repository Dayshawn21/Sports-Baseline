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
 * The arrows' targets. The two-day view (no date) steps to yesterday and the day after
 * tomorrow, past the two days it already shows; a one-day view steps one day.
 */
export function tennisDateNeighbors(date: string | null, today: string): { previous: string, next: string } {
  return date === null
    ? { previous: shiftDate(today, -1), next: shiftDate(today, 2) }
    : { previous: shiftDate(date, -1), next: shiftDate(date, 1) }
}
