import type { NbaLineMove, NbaPropLine, NbaRecord, NbaSlateGame, NbaSlateGap } from '~/types/nba'
import { nbaMarketLabel } from '~/utils/nbaLineOnly'
import { hasKickedOff } from '~/utils/nflGame'
import { isResultPending } from '~/utils/slateOrder'
import { spreadLabel } from '~/utils/nflGameModel'
import { fmtAmerican } from '~/utils/odds'
import { gapShareOfLine, signedGapUnits } from '~/utils/gapUnits'
import { dayClockCt, latestTime, rowOddsAge } from '~/utils/slatePeriod'

export { parseSlateDate, slateDateLabel } from '~/utils/slateDates'

const MISSING = '--'
const CENTRAL = 'America/Chicago'

/**
 * `started`: tipped off but not yet completed. Scores load with the next morning's ingest, so it is not "live".
 * `pending`: over by the clock, still waiting on that ingest.
 */
export type NbaSlateCardState = 'upcoming' | 'started' | 'pending' | 'final' | 'off'

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
  /** The same fetch as epoch milliseconds, for the stale-odds check. */
  oddsUpdatedMs: number | null
}

function tipLabel(startUtc: string | null): string {
  const time = startUtc === null ? NaN : Date.parse(startUtc)
  return Number.isNaN(time) ? 'Tip time not set' : dayClockCt(time)
}

function cardState(game: NbaSlateGame, now: Date): { state: NbaSlateCardState, label: string | null } {
  if (game.status === 'completed') return { state: 'final', label: 'Final' }
  if (game.status === 'postponed') return { state: 'off', label: 'Postponed' }
  if (game.status === 'canceled') return { state: 'off', label: 'Canceled' }
  if (isResultPending(game.startUtc, now)) return { state: 'pending', label: 'Result pending' }
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

/** "opened DET -1.5", "no move", or null while only one row is stored. Stale odds never claim "no move": the line was not checked since. */
function openedLabel(item: NbaLineMove | null, format: (line: number) => string, stale: boolean): string | null {
  if (item === null || item.openFetchedAt === item.currentFetchedAt) return null
  if (item.openLine === item.currentLine) return stale ? null : 'no move'
  return `opened ${format(item.openLine)}`
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

function marketCells(game: NbaSlateGame, stale: boolean): NbaSlateCardCell[] | null {
  if (game.moneyline === null && game.spread === null && game.total === null) return null
  const spread = (line: number) => spreadLabel(line, game.homeTeam, game.awayTeam)
  const total = (line: number) => line.toFixed(1)
  return [
    { label: 'Spread', value: game.spread === null ? MISSING : spread(game.spread.homeLine), detail: openedLabel(move(game, 'spread'), spread, stale) },
    { label: 'Total', value: game.total === null ? MISSING : total(game.total.line), detail: openedLabel(move(game, 'total'), total, stale) },
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

/** `oddsStale` is the slate's stale-odds check; the game page leaves it off. */
export function nbaSlateCard(game: NbaSlateGame, now: Date, oddsStale = false): NbaSlateCardModel {
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
    market: state === 'off' ? null : marketCells(game, oddsStale && state !== 'final'),
    final: final ? finalCells(game) : null,
    props: propsLabel(game.propLineCount),
  }
}

export function nbaSlateSummary(games: NbaSlateGame[]): NbaSlateSummary {
  const times = games.flatMap(game => [game.moneyline, game.spread, game.total])
    .flatMap(market => market === null ? [] : [Date.parse(market.fetchedAt)])
    .filter(time => !Number.isNaN(time))
  const oddsUpdatedMs = times.length ? Math.max(...times) : null
  return {
    games: games.length,
    propLines: games.reduce((sum, game) => sum + game.propLineCount, 0),
    finals: games.filter(game => game.status === 'completed').length,
    oddsUpdated: oddsUpdatedMs === null ? null : dayClockCt(oddsUpdatedMs),
    oddsUpdatedMs,
  }
}

/** One digest box's display strings; gray, never a pick. */
export interface NbaSlateDigestItem {
  key: string
  gameId: number
  playerId: number
  playerName: string
  /** The stored market, for opening its drawer; `market` is its label. */
  marketKey: string
  market: string
  matchup: string
  /** Central tip time. */
  when: string
  line: string
  model: string
  /** Model minus line in the stat's units: "+2.3 pts". */
  gap: string
  /** The same gap as a share of the line: "10% of the line". */
  gapScaled: string | null
}

export interface NbaGapGame {
  gameId: number
  awayTeam: string
  homeTeam: string
  startUtc: string | null
  status: string
}

/** One game's digest under the slate's rule (`rank_slate_gaps`): standard lines with a projection before tip, by |gap| / line, one per player. */
export function nbaGameGaps(game: NbaGapGame, lines: NbaPropLine[], now: Date, limit = 4): NbaSlateGap[] {
  const startUtc = game.startUtc
  if (game.status !== 'scheduled' || startUtc === null || Date.parse(startUtc) <= now.getTime()) return []
  const ranked = lines
    .filter(line => line.oddsType === 'standard' && line.projection !== null && line.gap !== null && line.line > 0)
    .map(line => ({ line, share: Math.abs(line.gap ?? 0) / line.line }))
    .sort((a, b) => b.share - a.share || a.line.playerName.localeCompare(b.line.playerName) || a.line.market.localeCompare(b.line.market))
  const seen = new Set<number>()
  const items: NbaSlateGap[] = []
  for (const { line, share } of ranked) {
    if (seen.has(line.playerId)) continue
    seen.add(line.playerId)
    items.push({
      gameId: game.gameId, awayTeam: game.awayTeam, homeTeam: game.homeTeam, startUtc, playerId: line.playerId,
      playerName: line.playerName, market: line.market, line: line.line,
      projection: line.projection ?? 0, gap: line.gap ?? 0, gapShare: share,
    })
    if (items.length === limit) break
  }
  return items
}

/** The API's ranked digest, in its order; the ranking rule lives server-side (`nba_slate_gaps`). */
const NBA_UNITS: Record<string, string> = { points: 'pts', rebounds: 'reb', assists: 'ast', threes_made: '3PM', blocks: 'blk' }

export function nbaSlateDigest(items: NbaSlateGap[]): NbaSlateDigestItem[] {
  return items.map(item => ({
    key: `${item.gameId}-${item.playerId}-${item.market}`,
    gameId: item.gameId,
    playerId: item.playerId,
    playerName: item.playerName,
    marketKey: item.market,
    market: nbaMarketLabel(item.market),
    matchup: `${item.awayTeam} @ ${item.homeTeam}`,
    when: tipLabel(item.startUtc),
    line: item.line.toFixed(1),
    model: item.projection.toFixed(1),
    gap: signedGapUnits(item.gap, NBA_UNITS[item.market]),
    gapScaled: gapShareOfLine(item.gapShare),
  }))
}

export interface NbaSlateRowCell {
  value: string
  detail: string | null
}

/** One slate table row's display strings, from the card model so both read one state and final rule. */
export interface NbaSlateRowModel {
  gameId: number
  state: NbaSlateCardState
  /** Central clock, else Final, Postponed or Canceled. */
  tip: string
  away: NbaSlateCardTeam
  home: NbaSlateCardTeam
  /** Market lines with their opening move, or the close graded against a final score. */
  spread: NbaSlateRowCell
  total: NbaSlateRowCell
  /** Favorite first; "--" once final or off. */
  moneyline: NbaSlateRowCell
  /** Market de-vigged win probability, favorite first, muted; null without a moneyline, final or off. */
  win: string | null
  props: number
  tags: string[]
  note: string | null
  /** "as of Tue" while the slate's odds are stale, for a game with a market that is not final or off; else null. */
  oddsAge: string | null
}

const NO_CELL: NbaSlateRowCell = { value: MISSING, detail: null }

function cellOf(cells: NbaSlateCardCell[] | null, label: string): NbaSlateRowCell {
  const cell = cells?.find(item => item.label === label)
  return cell === undefined ? NO_CELL : { value: cell.value, detail: cell.detail }
}

function winLabel(card: NbaSlateCardModel): string | null {
  if (card.winBar === null || card.state === 'final') return null
  const { away, home } = card.winBar
  return home >= away ? `${card.home.code} ${home}%` : `${card.away.code} ${away}%`
}

/** `staleSince` is the slate's newest fetch while its odds are stale. */
export function nbaSlateRow(game: NbaSlateGame, now: Date, staleSince: number | null = null): NbaSlateRowModel {
  const card = nbaSlateCard(game, now, staleSince !== null)
  const final = card.state === 'final'
  const off = card.state === 'off'
  const started = card.state === 'started'
  const pending = card.state === 'pending'
  return {
    gameId: card.gameId,
    state: card.state,
    tip: final || off ? card.stateLabel ?? MISSING : card.tip,
    away: card.away,
    home: card.home,
    spread: cellOf(final ? card.final : card.market, final ? 'Close spread' : 'Spread'),
    total: cellOf(final ? card.final : card.market, final ? 'Close total' : 'Total'),
    moneyline: final ? NO_CELL : cellOf(card.market, 'Moneyline'),
    win: winLabel(card),
    props: game.propLineCount,
    tags: started || pending ? [card.stateLabel ?? 'Tipped off'] : [],
    note: started || pending ? 'Scores load the morning after' : null,
    oddsAge: staleSince !== null && !final && !off && !pending && card.market !== null
      ? rowOddsAge(latestTime([game.spread?.fetchedAt, game.total?.fetchedAt, game.moneyline?.fetchedAt]), staleSince, now.getTime())
      : null,
  }
}
