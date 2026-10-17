import type { NbaLineMove, NbaRecord, NbaSlateGame } from '~/types/nba'
import { hasKickedOff } from '~/utils/nflGame'
import { spreadLabel } from '~/utils/nflGameModel'
import { fmtAmerican } from '~/utils/odds'

const MISSING = '--'
const CENTRAL = 'America/Chicago'
const CENTRAL_TIME = new Intl.DateTimeFormat('en-US', { timeZone: CENTRAL, weekday: 'short', hour: 'numeric', minute: '2-digit' })
// A slate date is a calendar date, so it is formatted in UTC to keep the day it names.
const SLATE_DAY = new Intl.DateTimeFormat('en-US', { timeZone: 'UTC', weekday: 'short', month: 'short', day: 'numeric', year: 'numeric' })

/** `started`: tipped off but not yet completed. Scores load with the next morning's ingest, so it is not "live". */
export type NbaSlateCardState = 'upcoming' | 'started' | 'final' | 'off'

export interface NbaSlateCardTeam {
  code: string
  name: string
  record: string
  /** Null until the game is final. */
  score: number | null
  lost: boolean
}

export interface NbaSlateCardCell {
  label: string
  value: string
  detail: string | null
}

/** One slate card's display strings; display only, never an input to an edge or rank. */
export interface NbaSlateCardModel {
  gameId: number
  state: NbaSlateCardState
  stateLabel: string | null
  tip: string
  away: NbaSlateCardTeam
  home: NbaSlateCardTeam
  /** Market de-vigged win probability in whole percent; null without a moneyline. */
  winBar: { away: number, home: number } | null
  /** Spread, total and moneyline; null when no market is stored, or the game is off. */
  market: NbaSlateCardCell[] | null
  /** Closing lines graded against the score; null unless final with a stored closing line. */
  final: NbaSlateCardCell[] | null
  props: string
}

export interface NbaSlateSummary {
  games: number
  propLines: number
  finals: number
  /** Latest stored market fetch in CT; null when no game has a market. */
  oddsUpdated: string | null
}

/** A `YYYY-MM-DD` link value naming a real date, else null. */
export function parseSlateDate(value: string | null): string | null {
  if (value === null || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return null
  const time = Date.parse(`${value}T00:00:00Z`)
  return !Number.isNaN(time) && new Date(time).toISOString().slice(0, 10) === value ? value : null
}

/** `Tue, Oct 20, 2026` */
export function slateDateLabel(date: string): string {
  return SLATE_DAY.format(Date.parse(`${date}T00:00:00Z`))
}

function tipLabel(startUtc: string | null): string {
  const time = startUtc === null ? NaN : Date.parse(startUtc)
  return Number.isNaN(time) ? 'Tip time not set' : `${CENTRAL_TIME.format(time)} CT`
}

function cardState(game: NbaSlateGame, now: Date): { state: NbaSlateCardState, label: string | null } {
  if (game.status === 'completed') return { state: 'final', label: 'Final' }
  if (game.status === 'postponed') return { state: 'off', label: 'Postponed' }
  if (game.status === 'canceled') return { state: 'off', label: 'Canceled' }
  return hasKickedOff(game.startUtc, now) ? { state: 'started', label: 'Tipped off' } : { state: 'upcoming', label: null }
}

function recordLabel(record: NbaRecord): string {
  return record.wins + record.losses === 0 ? 'No games yet' : `${record.wins}-${record.losses}`
}

function cardTeam(code: string, name: string, record: NbaRecord, score: number | null, otherScore: number | null, final: boolean): NbaSlateCardTeam {
  return {
    code, name, record: recordLabel(record),
    score: final ? score : null,
    lost: final && score !== null && otherScore !== null && score < otherScore,
  }
}

function move(game: NbaSlateGame, market: NbaLineMove['market']): NbaLineMove | null {
  return game.lineMovement.find(item => item.market === market) ?? null
}

/** "opened DET -1.5", "no move", or null while only one row is stored. */
function openedLabel(item: NbaLineMove | null, format: (line: number) => string): string | null {
  if (item === null || item.openFetchedAt === item.currentFetchedAt) return null
  return item.openLine === item.currentLine ? 'no move' : `opened ${format(item.openLine)}`
}

function moneylineCell(game: NbaSlateGame): NbaSlateCardCell {
  if (game.moneyline === null) return { label: 'Moneyline', value: MISSING, detail: null }
  const { homeOdds: home, awayOdds: away } = game.moneyline
  // The lower American price is the favorite; a pick'em shows the home side first.
  const homeFavored = home <= away
  const favorite = homeFavored ? `${game.homeTeam} ${fmtAmerican(home)}` : `${game.awayTeam} ${fmtAmerican(away)}`
  const other = homeFavored ? `${game.awayTeam} ${fmtAmerican(away)}` : `${game.homeTeam} ${fmtAmerican(home)}`
  return { label: 'Moneyline', value: favorite, detail: other }
}

function marketCells(game: NbaSlateGame): NbaSlateCardCell[] | null {
  if (game.moneyline === null && game.spread === null && game.total === null) return null
  const spread = (line: number) => spreadLabel(line, game.homeTeam, game.awayTeam)
  const total = (line: number) => line.toFixed(1)
  return [
    { label: 'Spread', value: game.spread === null ? MISSING : spread(game.spread.homeLine), detail: openedLabel(move(game, 'spread'), spread) },
    { label: 'Total', value: game.total === null ? MISSING : total(game.total.line), detail: openedLabel(move(game, 'total'), total) },
    moneylineCell(game),
  ]
}

function winBar(game: NbaSlateGame): NbaSlateCardModel['winBar'] {
  if (game.moneyline === null) return null
  const home = Math.round(game.moneyline.homeWinProbability * 100)
  return { away: 100 - home, home }
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

function finalCells(game: NbaSlateGame): NbaSlateCardCell[] | null {
  const { awayScore, homeScore, homeTeam, awayTeam } = game
  const spread = move(game, 'spread')
  const total = move(game, 'total')
  if (awayScore === null || homeScore === null || (spread === null && total === null)) return null
  const cells: NbaSlateCardCell[] = []
  if (spread !== null) {
    cells.push({
      label: 'Close spread',
      value: spreadLabel(spread.currentLine, homeTeam, awayTeam),
      detail: spreadResult(spread.currentLine, homeScore - awayScore, homeTeam, awayTeam),
    })
  }
  if (total !== null) {
    cells.push({ label: 'Close total', value: total.currentLine.toFixed(1), detail: totalResult(total.currentLine, homeScore + awayScore) })
  }
  cells.push({ label: 'Props', value: String(game.propLineCount), detail: 'lines' })
  return cells
}

function propsLabel(count: number): string {
  if (count === 0) return 'No prop lines stored yet'
  return count === 1 ? '1 prop line' : `${count} prop lines`
}

export function nbaSlateCard(game: NbaSlateGame, now: Date): NbaSlateCardModel {
  const { state, label } = cardState(game, now)
  const final = state === 'final'
  return {
    gameId: game.gameId,
    state,
    stateLabel: label,
    tip: tipLabel(game.startUtc),
    away: cardTeam(game.awayTeam, game.awayTeamName, game.awayRecord, game.awayScore, game.homeScore, final),
    home: cardTeam(game.homeTeam, game.homeTeamName, game.homeRecord, game.homeScore, game.awayScore, final),
    winBar: state === 'off' ? null : winBar(game),
    market: state === 'off' ? null : marketCells(game),
    final: final ? finalCells(game) : null,
    props: propsLabel(game.propLineCount),
  }
}

export function nbaSlateSummary(games: NbaSlateGame[]): NbaSlateSummary {
  const times = games.flatMap(game => [game.moneyline, game.spread, game.total])
    .flatMap(market => market === null ? [] : [Date.parse(market.fetchedAt)])
    .filter(time => !Number.isNaN(time))
  return {
    games: games.length,
    propLines: games.reduce((sum, game) => sum + game.propLineCount, 0),
    finals: games.filter(game => game.status === 'completed').length,
    oddsUpdated: times.length ? `${CENTRAL_TIME.format(Math.max(...times))} CT` : null,
  }
}
