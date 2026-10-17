import type { NflGameNotes, NflGameOdds, NflLineMove, NflSlateGame, NflTeamContext, NflTeamForm } from '~/types/nfl'
import { conditionsLabel, hasKickedOff, kickoffLabel, recordLabel } from '~/utils/nflGame'
import { bookLabel, sideLabel } from '~/utils/nflBestLine'
import { nflGameModelSummary, qbChanges, spreadLabel } from '~/utils/nflGameModel'
import { gameBoardAsOf } from '~/utils/nflGameProps'
import { marketLabel } from '~/utils/nflLabels'
import { edgePctLabel } from '~/utils/nflSignal'
import { devigP1, fmtAmerican } from '~/utils/odds'
import { buildNflPropBoard, compareBoardTiers, edgeShare, type NflBoardCategory, type NflBoardLine } from '~/utils/nflPropBoard'
import { groupNflPropRows } from '~/utils/nflPropRows'

const CENTRAL = 'America/Chicago'
const PRIME_TIME_HOUR = 18
const PRIME_TIME_DAYS = new Set(['Sunday', 'Monday'])
const UNSCHEDULED_KEY = 'unscheduled'
const PRIME_TIME_KEY = 'prime-time'

const WEEKDAY = new Intl.DateTimeFormat('en-US', { timeZone: CENTRAL, weekday: 'long' })
const HOUR_24 = new Intl.DateTimeFormat('en-US', { timeZone: CENTRAL, hour: 'numeric', hourCycle: 'h23' })
const CLOCK = new Intl.DateTimeFormat('en-US', { timeZone: CENTRAL, hour: 'numeric', minute: '2-digit' })
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

export interface NflTopProp {
  row: NflBoardLine
  /** Edge over the category's reference line, as on the prop cards. */
  edgeShare: number | null
}

type BoardBuilder = (games: NflSlateGame[], position: 'all', now: Date) => NflBoardCategory[]

/**
 * Each game's week-wide board, read as the game page reads it: now for an upcoming game, just
 * before kickoff for a started one. Games sharing an as-of instant share one build, so an
 * all-upcoming week builds the board once rather than once per card.
 */
export function slateBoards(games: NflSlateGame[], now: Date, build: BoardBuilder = buildNflPropBoard): Map<number, NflBoardCategory[]> {
  const builds = new Map<number, NflBoardCategory[]>()
  const boards = new Map<number, NflBoardCategory[]>()
  for (const game of games) {
    const asOf = gameBoardAsOf(game, now)
    const board = builds.get(asOf.getTime()) ?? build(games, 'all', asOf)
    builds.set(asOf.getTime(), board)
    boards.set(game.gameId, board)
  }
  return boards
}

/** A game's strongest rateable lines, ranked by the board's tiers then edge share, one per player. */
export function topGameProps(categories: NflBoardCategory[], gameId: number, limit = 3): NflTopProp[] {
  const ranked = categories
    .flatMap(category => category.rateable
      .filter(row => row.gameId === gameId)
      .map(row => ({ row, edgeShare: edgeShare(row, category.referenceLine) })))
    .sort((left, right) => compareBoardTiers(left.row, right.row)
      || Math.abs(right.edgeShare ?? 0) - Math.abs(left.edgeShare ?? 0)
      || left.row.playerName.localeCompare(right.row.playerName)
      || left.row.lineId - right.row.lineId)
  const players = new Set<number>()
  const top: NflTopProp[] = []
  for (const item of ranked) {
    if (top.length === limit) break
    if (players.has(item.row.playerId)) continue
    players.add(item.row.playerId)
    top.push(item)
  }
  return top
}

const MISSING = '--'

export type NflSlateCardState = 'upcoming' | 'live' | 'final'

export interface NflSlateCardTeam {
  code: string
  record: string
  rest: string | null
  /** Null until the game is final. */
  score: number | null
  lost: boolean
}

export interface NflSlateCardCell {
  label: string
  value: string
  detail: string | null
}

export interface NflSlateCardProp {
  lineId: number
  playerName: string
  market: string
  line: string
  edge: string
}

/** One slate card's display strings; display only, never an input to an edge or rank. */
export interface NflSlateCardModel {
  gameId: number
  state: NflSlateCardState
  kickoff: string
  conditions: string
  /** Report statuses only; null while game notes are unavailable. */
  injuries: { out: number, doubtful: number, questionable: number } | null
  shortWeek: string[]
  /** Teams whose QB differs from the one the muted model was built on. */
  qbChange: string[]
  /** "Best DAL -8.5 DK · TB +9.5 B365"; null unless upcoming with a best spread. */
  bestSpread: string | null
  away: NflSlateCardTeam
  home: NflSlateCardTeam
  /** Market de-vigged win probability in whole percent; null without both moneylines. */
  winBar: { away: number, home: number } | null
  /** Spread, total and moneyline; null when no book odds are stored. */
  market: NflSlateCardCell[] | null
  model: { spread: string, total: string, winProbability: string } | null
  topProps: NflSlateCardProp[]
  rateableCount: number
  otherCount: number
  /** Closing lines graded against the score; null unless final with a stored score. */
  final: NflSlateCardCell[] | null
}

function cardState(game: NflSlateGame, now: Date): NflSlateCardState {
  if (game.status === 'completed') return 'final'
  return hasKickedOff(game.startUtc, now) ? 'live' : 'upcoming'
}

function cardTeam(code: string, context: NflTeamContext | null, form: NflTeamForm | undefined, score: number | null, otherScore: number | null): NflSlateCardTeam {
  const rest = form?.restDays
  return {
    code,
    record: recordLabel(context),
    rest: rest == null ? null : `rest ${rest}`,
    score,
    lost: score !== null && otherScore !== null && score < otherScore,
  }
}

function lineMove(notes: NflGameNotes | undefined, market: NflLineMove['market']): NflLineMove | null {
  return notes?.lineMovement.find(move => move.market === market) ?? null
}

/** "opened BUF -1.5", "no move", or null when only one line is stored. */
function openedLabel(move: NflLineMove | null, format: (line: number) => string): string | null {
  if (move === null || move.move === null) return null
  return move.move === 0 ? 'no move' : `opened ${format(move.openLine)}`
}

function moneylineCell(odds: NflGameOdds, homeTeam: string, awayTeam: string): NflSlateCardCell {
  const { homeMoneyline: home, awayMoneyline: away } = odds
  if (home === null || away === null) return { label: 'Moneyline', value: MISSING, detail: null }
  // The lower American price is the favorite; a pick'em shows the home side first.
  const homeFavored = home <= away
  const favorite = homeFavored ? `${homeTeam} ${fmtAmerican(home)}` : `${awayTeam} ${fmtAmerican(away)}`
  const other = homeFavored ? `${awayTeam} ${fmtAmerican(away)}` : `${homeTeam} ${fmtAmerican(home)}`
  return { label: 'Moneyline', value: favorite, detail: other }
}

function marketCells(game: NflSlateGame, notes: NflGameNotes | undefined): NflSlateCardCell[] | null {
  const { odds, homeTeam, awayTeam } = game
  if (odds === null) return null
  const spread = (line: number) => spreadLabel(line, homeTeam, awayTeam)
  return [
    { label: 'Spread', value: odds.homeSpread === null ? MISSING : spread(odds.homeSpread), detail: openedLabel(lineMove(notes, 'spread'), spread) },
    { label: 'Total', value: odds.total?.toFixed(1) ?? MISSING, detail: openedLabel(lineMove(notes, 'total'), line => line.toFixed(1)) },
    moneylineCell(odds, homeTeam, awayTeam),
  ]
}

function winBar(odds: NflGameOdds | null): NflSlateCardModel['winBar'] {
  const home = devigP1(odds?.homeMoneyline ?? null, odds?.awayMoneyline ?? null)
  if (home === null) return null
  const homePct = Math.round(home * 100)
  return { away: 100 - homePct, home: homePct }
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

function finalCells(game: NflSlateGame, notes: NflGameNotes | undefined, propCount: number): NflSlateCardCell[] | null {
  if (notes === undefined || notes.awayScore === null || notes.homeScore === null) return null
  const { homeTeam, awayTeam } = game
  const spread = lineMove(notes, 'spread')
  const total = lineMove(notes, 'total')
  const cells: NflSlateCardCell[] = []
  if (spread !== null) {
    cells.push({
      label: 'Close spread',
      value: spreadLabel(spread.currentLine, homeTeam, awayTeam),
      detail: spreadResult(spread.currentLine, notes.homeScore - notes.awayScore, homeTeam, awayTeam),
    })
  }
  if (total !== null) {
    cells.push({ label: 'Close total', value: total.currentLine.toFixed(1), detail: totalResult(total.currentLine, notes.homeScore + notes.awayScore) })
  }
  cells.push({ label: 'Props', value: String(propCount), detail: 'lines' })
  return cells
}

function injuryCounts(notes: NflGameNotes | undefined): NflSlateCardModel['injuries'] {
  if (notes === undefined) return null
  const count = (status: string) => notes.injuries.filter(injury => injury.injuryStatus === status).length
  return { out: count('Out'), doubtful: count('Doubtful'), questionable: count('Questionable') }
}

function bestSpread(notes: NflGameNotes | undefined, homeTeam: string, awayTeam: string): string | null {
  const spread = notes?.bestLine?.markets.find(market => market.market === 'spread')
  if (!spread) return null
  return `Best ${spread.sides.map(side => `${sideLabel(side, homeTeam, awayTeam)} ${bookLabel(side.book, true)}`).join(' · ')}`
}

function modelCells(game: NflSlateGame): NflSlateCardModel['model'] {
  const summary = nflGameModelSummary(game.model, game.odds, game.homeTeam, game.awayTeam)
  if (summary === null) return null
  return { spread: summary.spread.model, total: summary.total.model, winProbability: summary.winProbability.model }
}

/** One slate card, from the slate game, its game notes, and the game's week-wide board (see `slateBoards`). */
export function nflSlateCard(game: NflSlateGame, notes: NflGameNotes | undefined, categories: NflBoardCategory[], now: Date): NflSlateCardModel {
  const state = cardState(game, now)
  const inGame = (row: NflBoardLine) => row.gameId === game.gameId
  const rateableCount = categories.reduce((sum, category) => sum + category.rateable.filter(inGame).length, 0)
  const otherCount = categories.reduce((sum, category) => sum + category.other.filter(inGame).length, 0)
  const awayScore = notes?.awayScore ?? null
  const homeScore = notes?.homeScore ?? null
  return {
    gameId: game.gameId,
    state,
    kickoff: kickoffLabel(game.startUtc),
    conditions: conditionsLabel(game.weather),
    injuries: injuryCounts(notes),
    shortWeek: [notes?.awayForm, notes?.homeForm].flatMap(form => form?.shortWeek ? [form.team] : []),
    qbChange: qbChanges(notes).map(change => change.team),
    bestSpread: state === 'upcoming' ? bestSpread(notes, game.homeTeam, game.awayTeam) : null,
    away: cardTeam(game.awayTeam, game.awayContext, notes?.awayForm, awayScore, homeScore),
    home: cardTeam(game.homeTeam, game.homeContext, notes?.homeForm, homeScore, awayScore),
    winBar: winBar(game.odds),
    market: marketCells(game, notes),
    model: modelCells(game),
    topProps: state === 'final' ? [] : topGameProps(categories, game.gameId).map(({ row, edgeShare: share }) => ({
      lineId: row.lineId,
      playerName: row.playerName,
      market: marketLabel(row.market),
      line: row.line?.toFixed(1) ?? MISSING,
      edge: edgePctLabel(share),
    })),
    rateableCount,
    otherCount,
    final: state === 'final' ? finalCells(game, notes, rateableCount + otherCount) : null,
  }
}
