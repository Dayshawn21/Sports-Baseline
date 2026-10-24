const SLATE_DAY = new Intl.DateTimeFormat('en-US', {
  timeZone: 'UTC', weekday: 'short', month: 'short', day: 'numeric', year: 'numeric',
})

/** A real calendar date in YYYY-MM-DD form, else null. */
export function parseSlateDate(value: string | null): string | null {
  if (value === null || !/^\d{4}-\d{2}-\d{2}$/.test(value) || value.startsWith('0000-')) return null
  const time = Date.parse(`${value}T00:00:00Z`)
  return !Number.isNaN(time) && new Date(time).toISOString().slice(0, 10) === value ? value : null
}

/** Calendar dates keep their named day regardless of the browser timezone. */
export function slateDateLabel(date: string): string {
  return SLATE_DAY.format(Date.parse(`${date}T00:00:00Z`))
}
