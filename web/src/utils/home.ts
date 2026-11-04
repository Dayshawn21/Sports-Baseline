import { SPORTS, VIEW_LABELS, sportViews, type Sport, type SportView } from '~/utils/sportNav'
import type { HomeSource } from '~/utils/homeSources'

export type HomeStatus = 'loading' | 'error' | 'ready'

export interface HomeSportData {
  sport: Sport
  status: HomeStatus
  /** Games on the slate (tennis: priced matches), finished ones included. */
  gameCount: number
  /** Start times in epoch ms of the games still to come; the caller drops finished ones. */
  startsMs: number[]
}

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

export function centralDay(startMs: number): string {
  return DAY_KEY.format(startMs)
}

export function weekdayLabel(startMs: number): string {
  return WEEKDAY.format(startMs)
}

/** Central time of day, with the weekday when the start is not today. */
export function startLabel(startMs: number, now: number): string {
  const clock = CLOCK.format(startMs)
  return DAY_KEY.format(startMs) === DAY_KEY.format(now) ? clock : `${WEEKDAY.format(startMs)} ${clock}`
}

const NOUN: Record<Sport, { one: string, many: string }> = {
  nfl: { one: 'game', many: 'games' },
  nba: { one: 'game', many: 'games' },
  nhl: { one: 'game', many: 'games' },
  tennis: { one: 'match', many: 'matches' },
}

function emptyText(sport: Sport): string {
  if (sport === 'tennis') return 'No priced matches'
  return sport === 'nhl' ? 'No games today' : 'No games scheduled'
}

export function sportNoun(sport: Sport, count: number): string {
  return count === 1 ? NOUN[sport].one : NOUN[sport].many
}

/** The page head's status line: today's date and time in Central, then when the newest slate loaded. */
export function todayStatus(now: number, refreshedMs: number | null): string {
  const when = `${WEEKDAY.format(now)} ${MONTH_DAY.format(now)} · ${CLOCK.format(now)} CT`
  return refreshedMs === null ? when : `${when} · slates refreshed ${CLOCK.format(refreshedMs)}`
}

/** The newest load time among the slate queries; react-query reports 0 for one that has not loaded. */
export function newestUpdate(times: number[]): number | null {
  const loaded = times.filter(time => time > 0)
  return loaded.length === 0 ? null : Math.max(...loaded)
}

const START_WORD: Record<Sport, string> = { nfl: 'Next kickoff', nba: 'First tip', nhl: 'First puck', tennis: 'First match' }

export type CardTone = 'normal' | 'quiet' | 'error' | 'loading'

export interface HomeCardLink { view: SportView, label: string, path: string }

/** Everything one sport card shows; the component only lays it out. */
export interface HomeCard {
  sport: Sport
  label: string
  /** The prototype's small caps tag: the NFL week, or TODAY for day-based sports. */
  period: string
  /** The start line, or the quiet text when there is nothing to start. */
  when: string
  count: string
  noun: string
  next: string
  tone: CardTone
  links: HomeCardLink[]
}

function cardWhen(data: HomeSportData, now: number): { text: string, tone: CardTone } {
  const { sport } = data
  if (data.status === 'loading') return { text: 'Loading', tone: 'loading' }
  if (data.status === 'error') return { text: 'Could not load', tone: 'error' }
  if (data.gameCount === 0) return { text: emptyText(sport), tone: 'quiet' }
  const start = nextStart(data, now)
  if (start === null) return { text: `No upcoming ${NOUN[sport].many}`, tone: 'quiet' }
  return { text: `${START_WORD[sport]} ${startLabel(start, now)} CT`, tone: 'normal' }
}

/** The NFL names a day's game when it has one and counts the rest; other sports list their next games. */
function nextLine(sport: Sport, source: HomeSource): string {
  if (sport === 'nfl') {
    return source.days.map(day => day.count === 1 ? `${day.label}: ${day.title}` : `${day.label}: ${day.count} games`).join(' · ')
  }
  return source.nextGames.length === 0 ? '' : `Next: ${source.nextGames.map(game => game.title).join(', ')}`
}

export function homeCard(data: HomeSportData, source: HomeSource, now: number): HomeCard {
  const { sport } = data
  const when = cardWhen(data, now)
  const ready = data.status === 'ready'
  const priced = sport === 'tennis' ? ' priced' : ''
  return {
    sport,
    label: SPORTS.find(entry => entry.code === sport)!.label,
    period: source.period?.toUpperCase() ?? 'TODAY',
    when: when.text,
    count: ready ? String(data.gameCount) : '--',
    noun: `${sportNoun(sport, data.gameCount)}${priced}`,
    next: ready ? nextLine(sport, source) : '',
    tone: when.tone,
    links: sportViews(sport).map(({ view, path }) => ({ view, label: VIEW_LABELS[view], path })),
  }
}
