import type { PlayerEloPoint, PlayerSurface, ServeReturnMetric, WinLoss } from '~/types/tennis'
import { parseMatchId } from '~/utils/tennisMatch'

/** Player ids follow the same positive-integer rule as match ids. */
export const parsePlayerId = parseMatchId

/** Whole years between a YYYY-MM-DD birth date and `now`, or null without a date. */
export function ageOn(birthDate: string | null, now: Date): number | null {
  const match = birthDate ? /^(\d{4})-(\d{2})-(\d{2})/.exec(birthDate) : null
  if (!match) return null
  const [year, month, day] = match.slice(1).map(Number)
  const beforeBirthday = now.getUTCMonth() + 1 < month || (now.getUTCMonth() + 1 === month && now.getUTCDate() < day)
  return now.getUTCFullYear() - year - (beforeBirthday ? 1 : 0)
}

export function recordText({ wins, losses }: WinLoss): string {
  const total = wins + losses
  if (total === 0) return '—'
  return `${wins}-${losses} · ${Math.round((wins / total) * 100)}%`
}

interface MetricSpec {
  metric: ServeReturnMetric
  label: string
  /** The value that fills the bar. Ace and DF rates are per serve point, so they run far below 1. */
  scale: number
  kind: 'pct' | 'rate'
}

/** Labels follow what the columns hold, not their names (open question 30). */
export const SERVE_RETURN_METRICS: MetricSpec[] = [
  { metric: 'holdPct', label: 'Hold', scale: 1, kind: 'pct' },
  { metric: 'breakPct', label: 'BP converted', scale: 1, kind: 'pct' },
  { metric: 'firstInPct', label: '1st serve in', scale: 1, kind: 'pct' },
  { metric: 'firstWonPct', label: '1st serve won', scale: 1, kind: 'pct' },
  { metric: 'secondWonPct', label: '2nd serve won', scale: 1, kind: 'pct' },
  { metric: 'retPtsWon', label: 'Return pts won', scale: 1, kind: 'pct' },
  { metric: 'acesPerGame', label: 'Ace rate', scale: 0.25, kind: 'rate' },
  { metric: 'dfPerGame', label: 'DF rate', scale: 0.1, kind: 'rate' },
]

/** Bar width in percent of the metric's scale, clamped to 0..100; null when there is no value. */
export function metricBar(value: number | null, metric: ServeReturnMetric): number | null {
  if (value == null) return null
  const spec = SERVE_RETURN_METRICS.find((s) => s.metric === metric)
  const scale = spec?.scale ?? 1
  return Math.min(100, Math.max(0, (value / scale) * 100))
}

export function metricText(value: number | null, metric: ServeReturnMetric): string {
  if (value == null) return '—'
  const kind = SERVE_RETURN_METRICS.find((s) => s.metric === metric)?.kind
  return kind === 'rate' ? `${(value * 100).toFixed(1)}%` : `${Math.round(value * 100)}%`
}

/** The serve-and-return tab to open first: the next match's surface, else all surfaces. */
export function defaultSurface(nextSurface: string | null | undefined): PlayerSurface {
  return nextSurface === 'Hard' || nextSurface === 'Clay' || nextSurface === 'Grass' ? nextSurface : 'all'
}

export type EloKey = 'overall' | 'hard' | 'clay' | 'grass'

/** The dashed surface line on the ELO chart: the next match's surface, else hard. */
export function chartSurface(nextSurface: string | null | undefined): Exclude<EloKey, 'overall'> {
  const surface = defaultSurface(nextSurface)
  return surface === 'all' ? 'hard' : (surface.toLowerCase() as Exclude<EloKey, 'overall'>)
}

export interface ChartBox {
  left: number
  right: number
  top: number
  bottom: number
}

export interface EloChart {
  series: Record<string, { x: number, y: number }[]>
  ticks: { value: number, y: number }[]
  dates: { label: string, x: number }[]
}

const ELO_PADDING = 10

/** Points placed by date on x and rating on y, with three rounded y ticks. */
export function eloChart(history: PlayerEloPoint[], keys: EloKey[], box: ChartBox): EloChart | null {
  const values = history.flatMap((p) => keys.map((k) => p[k]).filter((v): v is number => v != null))
  if (values.length === 0) return null
  const low = Math.floor((Math.min(...values) - ELO_PADDING) / 10) * 10
  const high = Math.ceil((Math.max(...values) + ELO_PADDING) / 10) * 10
  const times = history.map((p) => Date.parse(p.asOf))
  const first = Math.min(...times)
  const span = Math.max(...times) - first
  const xAt = (t: number) => (span === 0 ? (box.left + box.right) / 2 : box.left + ((t - first) / span) * (box.right - box.left))
  const yAt = (v: number) => box.bottom - ((v - low) / (high - low)) * (box.bottom - box.top)

  const series: EloChart['series'] = {}
  for (const key of keys) {
    series[key] = history.flatMap((p, i) => (p[key] == null ? [] : [{ x: xAt(times[i]), y: yAt(p[key] as number) }]))
  }
  const mid = Math.round((low + high) / 2)
  const fmt = new Intl.DateTimeFormat('en-US', { month: 'short', year: '2-digit', timeZone: 'UTC' })
  const edgeDates = span === 0 ? [first] : [first, first + span]
  return {
    series,
    ticks: [high, mid, low].map((value) => ({ value, y: yAt(value) })),
    dates: edgeDates.map((t) => ({ label: fmt.format(new Date(t)).replace(' ', " '"), x: xAt(t) })),
  }
}

const SHORT_DATE = new Intl.DateTimeFormat('en-US', { month: 'short', day: 'numeric', timeZone: 'UTC' })

/** "Sep 25" from a plain YYYY-MM-DD date, read in UTC so it never shifts a day in Central time. */
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

/** "3/4" for a box-score count over its opportunities, or a dash when either is missing. */
export function ratio(made: number | null, of: number | null): string {
  return made == null || of == null ? '—' : `${made}/${of}`
}
