/** Surface → display string with capitalization */
export function fmtSurface(surface: string | null | undefined): string {
  if (!surface) return '—'
  return surface.charAt(0).toUpperCase() + surface.slice(1).toLowerCase()
}

/** Tour badge color */
export function tourColor(tour: string): string {
  switch (tour.toUpperCase()) {
    case 'ATP': return '#1677ff'
    case 'WTA': return '#eb2f96'
    case 'CHALLENGER': return '#13a8a8'
    default: return '#666'
  }
}

/** Shorten a long tournament name for display */
export function fmtTournament(name: string | null | undefined, maxLen = 30): string {
  if (!name) return '—'
  return name.length > maxLen ? name.slice(0, maxLen - 1) + '…' : name
}

/** Format an ISO datetime string as Central Time, e.g. "3:30 PM CT" */
export function fmtTimeCT(iso: string | null | undefined): string {
  if (!iso) return ''
  const ts = Date.parse(iso)
  if (Number.isNaN(ts)) return ''
  return new Intl.DateTimeFormat('en-US', {
    timeZone: 'America/Chicago',
    hour: 'numeric',
    minute: '2-digit',
    hour12: true,
  }).format(new Date(ts)) + ' CT'
}

/** Format an ISO datetime string as a short date in CT, e.g. "Sat Apr 12" */
export function fmtDateCT(iso: string | null | undefined): string {
  if (!iso) return ''
  const ts = Date.parse(iso)
  if (Number.isNaN(ts)) return ''
  return new Intl.DateTimeFormat('en-US', {
    timeZone: 'America/Chicago',
    weekday: 'short',
    month: 'short',
    day: 'numeric',
  }).format(new Date(ts))
}

const CT_DAY_KEY_FMT = new Intl.DateTimeFormat('en-CA', {
  timeZone: 'America/Chicago',
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
})

/** YYYY-MM-DD for the CT calendar day a timestamp falls on. */
function ctDayKey(ts: number): string {
  return CT_DAY_KEY_FMT.format(new Date(ts))
}

/**
 * Time in CT, prefixed with the day when it is not today, e.g.
 * "Tomorrow · 10:00 AM CT" or "Thu Aug 27 · 10:00 AM CT".
 *
 * Boards can show a date other than today (the picker defaults to whichever
 * day has cards), and a bare clock time reads as "later today" — so the day
 * is only omitted when it genuinely is today. Comparison is on the CT
 * calendar day, not a 24h offset, so 11pm today vs 1am tomorrow still differ.
 */
export function fmtStartCT(iso: string | null | undefined, now: number = Date.now()): string {
  if (!iso) return ''
  const ts = Date.parse(iso)
  if (Number.isNaN(ts)) return ''

  const time = fmtTimeCT(iso)
  const day = ctDayKey(ts)
  if (day === ctDayKey(now)) return time

  const tomorrow = ctDayKey(now + 24 * 60 * 60 * 1000)
  const label = day === tomorrow ? 'Tomorrow' : fmtDateCT(iso)
  return `${label} · ${time}`
}
