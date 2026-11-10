import { SPORTS, VIEW_LABELS, sportViews, type Sport, type SportView } from '~/utils/sportNav'
import type { HomeGap, HomeMoneyline, HomeNextGame, HomeSource } from '~/utils/homeSources'

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
  /** The next-games text; `nextSegments` joined, so a screen reader and a test read one string. */
  next: string
  /** The same text split so a matchup can carry its team logos. */
  nextSegments: HomeNextSegment[]
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

export type HomeNextSegment = { text: string } | { away: string, home: string }

/** A team game's "AWAY @ HOME" title as its two codes; anything else (tennis "A vs B") stays text. */
export function matchupSegment(title: string): HomeNextSegment {
  const parts = /^(\S+) @ (\S+)$/.exec(title)
  return parts === null ? { text: title } : { away: parts[1], home: parts[2] }
}

function joined(items: HomeNextSegment[][], separator: string): HomeNextSegment[] {
  return items.flatMap((item, index) => index === 0 ? item : [{ text: separator }, ...item])
}

export function nextSegmentsText(segments: HomeNextSegment[]): string {
  return segments.map(segment => 'text' in segment ? segment.text : `${segment.away} @ ${segment.home}`).join('')
}

/** The NFL names a day's game when it has one and counts the rest; other sports list their next games. */
function nextSegments(sport: Sport, source: HomeSource): HomeNextSegment[] {
  if (sport === 'nfl') {
    return joined(source.days.map(day => day.count === 1
      ? [{ text: `${day.label}: ` }, matchupSegment(day.title)]
      : [{ text: `${day.label}: ${day.count} games` }]), ' · ')
  }
  return source.nextGames.length === 0 ? [] : [{ text: 'Next: ' }, ...joined(source.nextGames.map(game => [matchupSegment(game.title)]), ', ')]
}

export function homeCard(data: HomeSportData, source: HomeSource, now: number): HomeCard {
  const { sport } = data
  const when = cardWhen(data, now)
  const ready = data.status === 'ready'
  const priced = sport === 'tennis' ? ' priced' : ''
  const segments = ready ? nextSegments(sport, source) : []
  return {
    sport,
    label: SPORTS.find(entry => entry.code === sport)!.label,
    period: source.period?.toUpperCase() ?? 'TODAY',
    when: when.text,
    count: ready ? String(data.gameCount) : '--',
    noun: `${sportNoun(sport, data.gameCount)}${priced}`,
    next: nextSegmentsText(segments),
    nextSegments: segments,
    tone: when.tone,
    links: sportViews(sport).map(({ view, path }) => ({ view, label: VIEW_LABELS[view], path })),
  }
}

export type GapTabKey = 'all' | Sport

const SPORT_TAB_ORDER: Sport[] = ['nfl', 'nba', 'nhl', 'tennis']

/** A sport's data and source, as the gaps tabs read them. */
export interface HomeSportView { data: HomeSportData, source: HomeSource }

export interface HomeGapTab {
  key: GapTabKey
  label: string
  /** The tab text: the label, then that sport's next start when it has one. */
  text: string
}

export interface GapsFooter { label: string, path: string }

export type GapKind = 'props' | 'ml'

export type GapsBody =
  | { kind: 'loading' }
  | { kind: 'error', text: string }
  | { kind: 'rows', rows: HomeGap[], empty: string, footer: GapsFooter | null }
  | { kind: 'moneyline', rows: HomeMoneyline[], empty: string, note: string, footer: GapsFooter | null }
  | { kind: 'games', intro: string, games: HomeNextGame[], empty: string, footer: GapsFooter }

export function parseGapKind(param: string | null): GapKind {
  return param === 'ml' ? 'ml' : 'props'
}

export function parseGapTab(param: string | null): GapTabKey {
  return SPORT_TAB_ORDER.find(sport => sport === param) ?? 'all'
}

function sportLabel(sport: Sport): string {
  return SPORTS.find(entry => entry.code === sport)!.label
}

export function gapTabs(sports: HomeSportView[], now: number): HomeGapTab[] {
  return [
    { key: 'all', label: 'All', text: 'All' },
    ...SPORT_TAB_ORDER.map(sport => {
      const label = sportLabel(sport)
      const data = sports.find(entry => entry.data.sport === sport)!.data
      const start = data.status === 'ready' ? nextStart(data, now) : null
      return { key: sport, label, text: start === null ? label : `${label} · ${startLabel(start, now)}` }
    }),
  ]
}

const GAMES_INTRO: Partial<Record<Sport, string>> = {
  nhl: 'NHL props are line-only with no model projection, so there are no gaps to show. Next games:',
}

function footerFor(sport: Sport, view: SportView): GapsFooter {
  const path = sportViews(sport).find(entry => entry.view === view)!.path
  const label = sportLabel(sport)
  return { label: view === 'props' ? `View all ${label} props` : `Open the ${label} slate`, path }
}

/** NFL rows then NBA rows, each in its own digest order: a share of a reference line and points never share a sort. */
export function allGapRows(sports: HomeSportView[]): HomeGap[] {
  return SPORT_TAB_ORDER.flatMap(sport => sports.find(entry => entry.data.sport === sport)!.source.gaps)
}

const NO_WIN_MODEL_INTRO: Partial<Record<Sport, string>> = {
  nba: 'NBA has no win-probability model, so there is no moneyline gap to show. Next games:',
  nhl: 'NHL has no win-probability model, so there is no moneyline gap to show. Next games:',
}

const MONEYLINE_NOTE: Partial<Record<Sport, string>> = {
  nfl: 'NFL win probability did not beat closing lines; reference only.',
  tennis: 'The tennis ensemble is not ahead of the market; reference only.',
}

const MONEYLINE_SPORTS: Sport[] = ['nfl', 'tennis']

function moneylineBody(tab: GapTabKey, sports: HomeSportView[]): GapsBody {
  if (tab === 'all') {
    const rows = MONEYLINE_SPORTS.flatMap(sport => sports.find(entry => entry.data.sport === sport)!.source.moneyline)
    return { kind: 'moneyline', rows, empty: 'No moneyline gaps yet.', note: MONEYLINE_SPORTS.map(sport => MONEYLINE_NOTE[sport]).join(' '), footer: null }
  }
  const { data, source } = sports.find(entry => entry.data.sport === tab)!
  const sport = data.sport
  const intro = NO_WIN_MODEL_INTRO[sport]
  if (intro !== undefined) {
    const empty = data.gameCount === 0 ? emptyText(sport) : `No upcoming ${NOUN[sport].many}`
    return { kind: 'games', intro, games: source.schedule, empty, footer: footerFor(sport, 'slate') }
  }
  const empty = data.gameCount === 0 ? emptyText(sport) : 'No moneyline gaps yet.'
  return { kind: 'moneyline', rows: source.moneyline, empty, note: MONEYLINE_NOTE[sport] ?? '', footer: footerFor(sport, 'slate') }
}

export function gapsBody(tab: GapTabKey, sports: HomeSportView[], kind: GapKind = 'props'): GapsBody {
  if (kind === 'ml') {
    if (tab !== 'all') {
      const { status } = sports.find(entry => entry.data.sport === tab)!.data
      if (status === 'loading') return { kind: 'loading' }
      if (status === 'error') return { kind: 'error', text: 'Could not load' }
    }
    return moneylineBody(tab, sports)
  }
  return propsBody(tab, sports)
}

function propsBody(tab: GapTabKey, sports: HomeSportView[]): GapsBody {
  if (tab === 'all') return { kind: 'rows', rows: allGapRows(sports), empty: 'No gap lines yet.', footer: null }
  const { data, source } = sports.find(entry => entry.data.sport === tab)!
  if (data.status === 'loading') return { kind: 'loading' }
  if (data.status === 'error') return { kind: 'error', text: 'Could not load' }
  const sport = data.sport
  const intro = GAMES_INTRO[sport]
  if (intro !== undefined) {
    const empty = data.gameCount === 0 ? emptyText(sport) : `No upcoming ${NOUN[sport].many}`
    return { kind: 'games', intro, games: source.schedule, empty, footer: footerFor(sport, 'props') }
  }
  const empty = source.gapsFailed ? 'Gap lines could not load.' : data.gameCount === 0 ? emptyText(sport) : 'No gap lines yet.'
  return { kind: 'rows', rows: source.gaps, empty, footer: footerFor(sport, 'props') }
}
