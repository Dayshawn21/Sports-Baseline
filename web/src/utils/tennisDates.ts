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
