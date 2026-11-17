/** Surface → display string with capitalization */
export function fmtSurface(surface: string | null | undefined): string {
  if (!surface) return '—'
  return surface.charAt(0).toUpperCase() + surface.slice(1).toLowerCase()
}

/** The owner reads every time in Central. */
export const CENTRAL_TZ = 'America/Chicago'

const TOUR_COLORS: Record<string, string> = {
  ATP: 'var(--atp-blue)',
  WTA: 'var(--wta-pink)',
  CHALLENGER: 'var(--challenger-teal)',
}

/** A tour's theme color, for tags and labels; an unknown tour reads as secondary text. */
export function tourColor(tour: string): string {
  return TOUR_COLORS[tour.toUpperCase()] ?? 'var(--text-secondary)'
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
    timeZone: CENTRAL_TZ,
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
    timeZone: CENTRAL_TZ,
    weekday: 'short',
    month: 'short',
    day: 'numeric',
  }).format(new Date(ts))
}

const CT_DAY_KEY_FMT = new Intl.DateTimeFormat('en-CA', {
  timeZone: CENTRAL_TZ,
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
})

/** YYYY-MM-DD for the CT calendar day a timestamp falls on. */
export function ctDayKey(ts: number): string {
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

/**
 * A signed number such as `+1.5`, `-0.42` or `+3.0%`. It rounds before signing, so a value that rounds to
 * zero (including -0) shows unsigned: `-0.0` reads as a loss and `+0.0` as a gain.
 */
export function fmtSigned(value: number, decimals = 1, suffix = ''): string {
  if (!Number.isFinite(value)) return `${value}${suffix}`
  const text = Math.abs(value).toFixed(decimals)
  if (Number(text) === 0) return `${text}${suffix}`
  return `${value > 0 ? '+' : '-'}${text}${suffix}`
}

const SHORT_DATE = new Intl.DateTimeFormat('en-US', { month: 'short', day: 'numeric', timeZone: 'UTC' })

/** "Sep 25" from a plain YYYY-MM-DD date (or a timestamp's date part), read in UTC so it never shifts a day. */
export function shortDate(isoDate: string): string {
  const ts = Date.parse(`${isoDate.slice(0, 10)}T00:00:00Z`)
  return Number.isNaN(ts) ? isoDate : SHORT_DATE.format(new Date(ts))
}

const DATE_WITH_YEAR = new Intl.DateTimeFormat('en-US', { month: 'short', day: 'numeric', year: 'numeric', timeZone: 'UTC' })

/** "Sep 29, 2025" from a plain YYYY-MM-DD date, for windows that reach into last year. */
export function dateWithYear(isoDate: string): string {
  const ts = Date.parse(`${isoDate.slice(0, 10)}T00:00:00Z`)
  return Number.isNaN(ts) ? isoDate : DATE_WITH_YEAR.format(new Date(ts))
}
