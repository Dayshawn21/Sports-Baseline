import { SPORTS, type Sport } from '~/utils/sportNav'

export type HomeStatus = 'loading' | 'error' | 'ready'

export interface HomeSportData {
  sport: Sport
  status: HomeStatus
  /** Games on the slate (tennis: priced matches), finished ones included. */
  gameCount: number
  /** Start times in epoch ms of the games still to come; the caller drops finished ones. */
  startsMs: number[]
}

/** Starts this close to the earliest one count as tied. */
export const LEAD_TIE_WINDOW_MS = 3 * 60 * 60 * 1000

/** A tie goes to a team sport first: tennis plays around the clock and would otherwise lead every day. */
const TIE_PRIORITY: readonly Sport[] = ['nfl', 'nba', 'nhl', 'tennis']

const CENTRAL = 'America/Chicago'
const CLOCK = new Intl.DateTimeFormat('en-US', { timeZone: CENTRAL, hour: 'numeric', minute: '2-digit' })
const WEEKDAY = new Intl.DateTimeFormat('en-US', { timeZone: CENTRAL, weekday: 'short' })
const MONTH_DAY = new Intl.DateTimeFormat('en-US', { timeZone: CENTRAL, month: 'short', day: 'numeric' })
const DAY_KEY = new Intl.DateTimeFormat('en-CA', { timeZone: CENTRAL })

/** Soonest start strictly after `now`, or null when nothing is left. */
export function nextStart(data: HomeSportData, now: number): number | null {
  const upcoming = data.startsMs.filter(start => start > now)
  return upcoming.length === 0 ? null : Math.min(...upcoming)
}

function readyStarts(data: HomeSportData[], now: number) {
  return data.flatMap(entry => {
    const start = entry.status === 'ready' ? nextStart(entry, now) : null
    return start === null ? [] : [{ sport: entry.sport, start }]
  })
}

/** The sport that leads the home, or null when no sport that loaded has a game still to come. */
export function chooseLead(data: HomeSportData[], now: number): Sport | null {
  const eligible = readyStarts(data, now)
  if (eligible.length === 0) return null
  const earliest = Math.min(...eligible.map(entry => entry.start))
  const tied = eligible.filter(entry => entry.start - earliest <= LEAD_TIE_WINDOW_MS)
  return tied.sort((a, b) => TIE_PRIORITY.indexOf(a.sport) - TIE_PRIORITY.indexOf(b.sport))[0].sport
}

/** The strip: every sport except the lead, soonest start first; sports with none to come go last in registry order. */
export function stripOrder(data: HomeSportData[], lead: Sport | null, now: number): HomeSportData[] {
  const registry = (entry: HomeSportData) => SPORTS.findIndex(sport => sport.code === entry.sport)
  return data
    .filter(entry => entry.sport !== lead)
    .map(entry => ({ entry, start: nextStart(entry, now) }))
    .sort((a, b) => (a.start ?? Infinity) - (b.start ?? Infinity) || registry(a.entry) - registry(b.entry))
    .map(({ entry }) => entry)
}

/** Central time of day, with the weekday when the start is not today. */
export function startLabel(startMs: number, now: number): string {
  const clock = CLOCK.format(startMs)
  return DAY_KEY.format(startMs) === DAY_KEY.format(now) ? clock : `${WEEKDAY.format(startMs)} ${clock}`
}

const NOUN: Record<Sport, { one: string, many: string, first: string }> = {
  nfl: { one: 'game', many: 'games', first: 'kickoff' },
  nba: { one: 'game', many: 'games', first: 'tip' },
  nhl: { one: 'game', many: 'games', first: 'puck' },
  tennis: { one: 'match', many: 'matches', first: 'match' },
}

export type StripTone = 'normal' | 'quiet' | 'error'
export interface StripRow { sport: Sport, text: string, tone: StripTone }

function emptyText(sport: Sport): string {
  if (sport === 'tennis') return 'No priced matches'
  return sport === 'nhl' ? 'No games today' : 'No games scheduled'
}

/** One "Also today" row; a sport that failed or is empty never blocks the others. */
export function stripRow(data: HomeSportData, now: number): StripRow {
  const { sport } = data
  if (data.status === 'loading') return { sport, text: 'Loading', tone: 'quiet' }
  if (data.status === 'error') return { sport, text: 'Could not load', tone: 'error' }
  if (data.gameCount === 0) return { sport, text: emptyText(sport), tone: 'quiet' }
  const noun = NOUN[sport]
  const start = nextStart(data, now)
  if (start === null) return { sport, text: `No upcoming ${noun.many}`, tone: 'quiet' }
  const count = `${data.gameCount} ${data.gameCount === 1 ? noun.one : noun.many}`
  return { sport, text: `${count} · first ${noun.first} ${startLabel(start, now)}`, tone: 'normal' }
}

/** The hero's subtitle: when the lead's next game starts. */
export function heroNext(sport: Sport, startMs: number, now: number): string {
  return `Next ${NOUN[sport].first} ${startLabel(startMs, now)} CT`
}

export function sportNoun(sport: Sport, count: number): string {
  return count === 1 ? NOUN[sport].one : NOUN[sport].many
}

/** The page head's status line: today's date and time in Central, then who has the next start. */
export function todayStatus(lead: string | null, now: number): string {
  const when = `${WEEKDAY.format(now)} ${MONTH_DAY.format(now)} · ${CLOCK.format(now)} CT`
  return lead === null ? when : `${when} · ${lead} has the next start`
}
