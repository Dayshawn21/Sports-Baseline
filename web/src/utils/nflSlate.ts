import type { NflGameNotes, NflGameOdds, NflLineMove, NflSlateGame, NflTeamContext } from '~/types/nfl'
import { conditionsLabel, hasKickedOff, recordLabel } from '~/utils/nflGame'
import { nflGameModelSummary, qbChanges, spreadLabel } from '~/utils/nflGameModel'
import { marketLabel } from '~/utils/nflLabels'
import { isTargetsReference } from '~/utils/nflTargets'
import { edgePctLabel } from '~/utils/nflSignal'
import { fmtAmerican } from '~/utils/odds'
import { compareBoardTiers, edgeShare, type NflBoardCategory, type NflBoardLine } from '~/utils/nflPropBoard'
import { groupNflPropRows } from '~/utils/nflPropRows'

const CENTRAL = 'America/Chicago'
const PRIME_TIME_HOUR = 18
const PRIME_TIME_DAYS = new Set(['Sunday', 'Monday'])
const UNSCHEDULED_KEY = 'unscheduled'
const PRIME_TIME_KEY = 'prime-time'

const WEEKDAY = new Intl.DateTimeFormat('en-US', { timeZone: CENTRAL, weekday: 'long' })
const HOUR_24 = new Intl.DateTimeFormat('en-US', { timeZone: CENTRAL, hour: 'numeric', hourCycle: 'h23' })
const CLOCK = new Intl.DateTimeFormat('en-US', { timeZone: CENTRAL, hour: 'numeric', minute: '2-digit' })
const DAY_CLOCK = new Intl.DateTimeFormat('en-US', { timeZone: CENTRAL, weekday: 'short', hour: 'numeric', minute: '2-digit' })
const UPDATED = new Intl.DateTimeFormat('en-US', { timeZone: CENTRAL, weekday: 'short', hour: 'numeric', minute: '2-digit' })

export interface NflKickoffWindow {
  key: string
  title: string
  subtitle: string
  games: NflSlateGame[]
}

export interface NflSlateSummary {
  games: number
  propLines: number
  finals: number
  /** Null while game notes are unavailable. */
  outOrDoubtful: number | null
  /** Latest pre-kickoff odds fetch in CT; null without notes or stored movement. */
  oddsUpdated: string | null
}

function kickoffTime(game: Pick<NflSlateGame, 'startUtc'>): number | null {
  if (game.startUtc === null) return null
  const time = Date.parse(game.startUtc)
  return Number.isNaN(time) ? null : time
}

function windowOf(time: number): { key: string, title: string, day: string } {
  const day = WEEKDAY.format(time)
  if (PRIME_TIME_DAYS.has(day) && Number(HOUR_24.format(time)) >= PRIME_TIME_HOUR) {
    return { key: PRIME_TIME_KEY, title: 'Prime time', day }
  }
  const clock = CLOCK.format(time)
  return { key: `${day} ${clock}`, title: `${day} · ${clock} CT`, day }
}

function gamesLabel(count: number): string {
  return `${count} game${count === 1 ? '' : 's'}`
}

function primeTimeLabel(days: Set<string>): string {
  const nights = [days.has('Sunday') && 'SNF', days.has('Monday') && 'MNF'].filter(Boolean)
  return nights.join(' and ')
}

/**
 * Groups a week into kickoff windows by Central-time weekday and kickoff. Sunday and Monday
 * night games share one "Prime time" window; a game with no kickoff time goes last.
 */
export function kickoffWindows(games: NflSlateGame[]): NflKickoffWindow[] {
  const ordered = [...games].sort((left, right) =>
    (kickoffTime(left) ?? Infinity) - (kickoffTime(right) ?? Infinity) || left.awayTeam.localeCompare(right.awayTeam))
  const windows = new Map<string, { title: string, days: Set<string>, games: NflSlateGame[] }>()
  for (const game of ordered) {
    const time = kickoffTime(game)
    const slot = time === null ? { key: UNSCHEDULED_KEY, title: 'Kickoff time not set', day: '' } : windowOf(time)
    const window = windows.get(slot.key) ?? { title: slot.title, days: new Set<string>(), games: [] }
    window.days.add(slot.day)
    window.games.push(game)
    windows.set(slot.key, window)
  }
  // A Map keeps insertion order, and games were inserted by kickoff, so windows follow their earliest game.
  return [...windows.entries()].map(([key, window]) => ({
    key,
    title: window.title,
    subtitle: key === PRIME_TIME_KEY ? `${primeTimeLabel(window.days)} · ${gamesLabel(window.games.length)}` : gamesLabel(window.games.length),
    games: window.games,
  }))
}

function latestOddsFetch(notes: NflGameNotes[]): string | null {
  const times = notes.flatMap(game => game.lineMovement.map(move => Date.parse(move.currentFetchedAt)))
    .filter(time => !Number.isNaN(time))
  return times.length ? `${UPDATED.format(Math.max(...times))} CT` : null
}

/** The slate's summary strip. `notes` is undefined until game notes load, or when they fail. */
export function nflSlateSummary(games: NflSlateGame[], notes: NflGameNotes[] | undefined): NflSlateSummary {
  return {
    games: games.length,
    propLines: groupNflPropRows(games.flatMap(game => game.lines)).length,
    finals: games.filter(game => game.status === 'completed').length,
    outOrDoubtful: notes === undefined ? null : notes.flatMap(game => game.injuries)
      .filter(injury => injury.injuryStatus === 'Out' || injury.injuryStatus === 'Doubtful').length,
    oddsUpdated: notes === undefined ? null : latestOddsFetch(notes),
  }
}

interface RankedProp {
  row: NflBoardLine
  edgeShare: number | null
}

/** Ranks rateable lines by the board's tiers then edge share, one per player: the old slate card's top-props order. */
function rankTopProps(categories: NflBoardCategory[], limit: number): RankedProp[] {
  const ranked = categories
    .flatMap(category => category.rateable.map(row => ({ row, edgeShare: edgeShare(row, category.referenceLine) })))
    .sort((left, right) => compareBoardTiers(left.row, right.row)
      || Math.abs(right.edgeShare ?? 0) - Math.abs(left.edgeShare ?? 0)
      || left.row.playerName.localeCompare(right.row.playerName)
      || left.row.lineId - right.row.lineId)
  const players = new Set<number>()
  const top: RankedProp[] = []
  for (const item of ranked) {
    if (top.length === limit) break
    if (players.has(item.row.playerId)) continue
    players.add(item.row.playerId)
    top.push(item)
  }
  return top
}

const MISSING = '--'

/** One plays-digest box; display strings only, gray, never a pick. */
export interface NflSlateDigestItem {
  lineId: number
  gameId: number
  playerName: string
  market: string
  matchup: string
  /** Central kickoff time. */
  when: string
  line: string
  model: string
  modelLabel?: string
  /** Signed edge share against the category's reference line, as on the prop cards. */
  gap: string
}

function digestKickoff(startUtc: string | null): string {
  const time = startUtc === null ? NaN : Date.parse(startUtc)
  return Number.isNaN(time) ? 'Kickoff time not set' : `${DAY_CLOCK.format(time)} CT`
}

/** The week's largest gaps, from a board built as of now (which already drops started games). */
export function slateDigest(categories: NflBoardCategory[], limit = 4): NflSlateDigestItem[] {
  return rankTopProps(categories, limit).map(({ row, edgeShare: share }) => ({
    lineId: row.lineId,
    gameId: row.gameId,
    playerName: row.playerName,
    market: isTargetsReference(row.market) ? `${marketLabel(row.market)} reference` : marketLabel(row.market),
    matchup: `${row.awayTeam} @ ${row.homeTeam}`,
    when: digestKickoff(row.startUtc),
    line: row.line?.toFixed(1) ?? MISSING,
    model: row.projection?.toFixed(1) ?? MISSING,
    ...(isTargetsReference(row.market) ? { modelLabel: 'reference' } : {}),
    gap: edgePctLabel(share),
  }))
}

export type NflSlateRowState = 'upcoming' | 'live' | 'final'

export interface NflSlateRowTeam {
  code: string
  record: string
  /** Null until the game is final. */
  score: number | null
  lost: boolean
}

export interface NflSlateRowCell {
  value: string
  detail: string | null
}

/** One slate table row's display strings; display only, never an input to an edge or rank. */
export interface NflSlateRowModel {
  gameId: number
  state: NflSlateRowState
  /** Central weekday and clock ("Sun 12:00 PM"; prime time spans two days); "--" when unscheduled. */
  kickoff: string
  away: NflSlateRowTeam
  home: NflSlateRowTeam
  /** Market lines with their opening move, or the close graded against a final score. */
  spread: NflSlateRowCell
  total: NflSlateRowCell
  /** Favorite first; "--" once final. */
  moneyline: NflSlateRowCell
  /** Muted nfl-elo-v1 spread and total; null when the model has no rating for a team. */
  model: { spread: string, total: string } | null
  /** Stored prop lines, counted as the summary strip counts them. */
  props: number
  conditions: string
  /** Report statuses only; null while game notes are unavailable or once final. */
  injuries: { out: number, doubtful: number, questionable: number } | null
  shortWeek: string[]
  /** Teams whose QB differs from the one the muted model was built on. */
  qbChange: string[]
}

const NO_CELL: NflSlateRowCell = { value: MISSING, detail: null }

function rowState(game: NflSlateGame, now: Date): NflSlateRowState {
  if (game.status === 'completed') return 'final'
  return hasKickedOff(game.startUtc, now) ? 'live' : 'upcoming'
}

function rowTeam(code: string, context: NflTeamContext | null, score: number | null, otherScore: number | null): NflSlateRowTeam {
  return { code, record: recordLabel(context), score, lost: score !== null && otherScore !== null && score < otherScore }
}

function lineMove(notes: NflGameNotes | undefined, market: NflLineMove['market']): NflLineMove | null {
  return notes?.lineMovement.find(move => move.market === market) ?? null
}

/** "opened BUF -1.5", "no move", or null when only one line is stored. */
function openedLabel(move: NflLineMove | null, format: (line: number) => string): string | null {
  if (move === null || move.move === null) return null
  return move.move === 0 ? 'no move' : `opened ${format(move.openLine)}`
}

function moneylineCell(odds: NflGameOdds | null, homeTeam: string, awayTeam: string): NflSlateRowCell {
  const home = odds?.homeMoneyline ?? null
  const away = odds?.awayMoneyline ?? null
  if (home === null || away === null) return NO_CELL
  // The lower American price is the favorite; a pick'em shows the home side first.
  const homeFavored = home <= away
  const favorite = homeFavored ? `${homeTeam} ${fmtAmerican(home)}` : `${awayTeam} ${fmtAmerican(away)}`
  const other = homeFavored ? `${awayTeam} ${fmtAmerican(away)}` : `${homeTeam} ${fmtAmerican(home)}`
  return { value: favorite, detail: other }
}

function marketSpread(game: NflSlateGame, notes: NflGameNotes | undefined): NflSlateRowCell {
  if (game.odds === null) return NO_CELL
  const spread = (line: number) => spreadLabel(line, game.homeTeam, game.awayTeam)
  return { value: game.odds.homeSpread === null ? MISSING : spread(game.odds.homeSpread), detail: openedLabel(lineMove(notes, 'spread'), spread) }
}

function marketTotal(game: NflSlateGame, notes: NflGameNotes | undefined): NflSlateRowCell {
  if (game.odds === null) return NO_CELL
  return { value: game.odds.total?.toFixed(1) ?? MISSING, detail: openedLabel(lineMove(notes, 'total'), line => line.toFixed(1)) }
}

/** Home spread in book sign: the home side covers when its margin plus the line is positive. */
function spreadResult(homeLine: number, homeMargin: number, homeTeam: string, awayTeam: string): string {
  const cover = homeMargin + homeLine
  if (cover === 0) return 'push'
  return `${cover > 0 ? homeTeam : awayTeam} covered`
}

function totalResult(line: number, points: number): string {
  const difference = points - line
  if (difference === 0) return 'push'
  return `${difference > 0 ? 'over' : 'under'} by ${Math.abs(difference).toFixed(1)}`
}

/** A final's closing spread, graded; "--" until both the score and a pre-kickoff line are stored. */
function closeSpread(game: NflSlateGame, notes: NflGameNotes | undefined): NflSlateRowCell {
  const spread = lineMove(notes, 'spread')
  if (!notes || spread === null || notes.awayScore === null || notes.homeScore === null) return NO_CELL
  const { homeTeam, awayTeam } = game
  return {
    value: spreadLabel(spread.currentLine, homeTeam, awayTeam),
    detail: spreadResult(spread.currentLine, notes.homeScore - notes.awayScore, homeTeam, awayTeam),
  }
}

function closeTotal(notes: NflGameNotes | undefined): NflSlateRowCell {
  const total = lineMove(notes, 'total')
  if (!notes || total === null || notes.awayScore === null || notes.homeScore === null) return NO_CELL
  return { value: total.currentLine.toFixed(1), detail: totalResult(total.currentLine, notes.awayScore + notes.homeScore) }
}

function injuryCounts(notes: NflGameNotes | undefined): NflSlateRowModel['injuries'] {
  if (notes === undefined) return null
  const count = (status: string) => notes.injuries.filter(injury => injury.injuryStatus === status).length
  return { out: count('Out'), doubtful: count('Doubtful'), questionable: count('Questionable') }
}

function modelLines(game: NflSlateGame): NflSlateRowModel['model'] {
  const summary = nflGameModelSummary(game.model, game.odds, game.homeTeam, game.awayTeam)
  if (summary === null) return null
  return { spread: summary.spread.model, total: summary.total.model }
}

function rowKickoff(game: NflSlateGame): string {
  const time = kickoffTime(game)
  return time === null ? MISSING : DAY_CLOCK.format(time).replace(',', '')
}

/** One slate row, from the slate game and its game notes. */
export function nflSlateRow(game: NflSlateGame, notes: NflGameNotes | undefined, now: Date): NflSlateRowModel {
  const state = rowState(game, now)
  const final = state === 'final'
  const awayScore = notes?.awayScore ?? null
  const homeScore = notes?.homeScore ?? null
  return {
    gameId: game.gameId,
    state,
    kickoff: final ? 'Final' : rowKickoff(game),
    away: rowTeam(game.awayTeam, game.awayContext, awayScore, homeScore),
    home: rowTeam(game.homeTeam, game.homeContext, homeScore, awayScore),
    spread: final ? closeSpread(game, notes) : marketSpread(game, notes),
    total: final ? closeTotal(notes) : marketTotal(game, notes),
    moneyline: final ? NO_CELL : moneylineCell(game.odds, game.homeTeam, game.awayTeam),
    model: modelLines(game),
    props: groupNflPropRows(game.lines).length,
    conditions: conditionsLabel(game.weather),
    injuries: final ? null : injuryCounts(notes),
    shortWeek: final ? [] : [notes?.awayForm, notes?.homeForm].flatMap(form => form?.shortWeek ? [form.team] : []),
    qbChange: final ? [] : qbChanges(notes).map(change => change.team),
  }
}
