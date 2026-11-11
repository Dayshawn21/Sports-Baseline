import type { NflSlateGame, NflSlateLine } from '~/types/nfl'
import { MIN_BASELINE_GAMES, STALE_FLAG } from '~/utils/nflBaseline'
import { MARKET_LABELS } from '~/utils/nflLabels'
import { filterNflSlateLinesByPosition, type NflPositionFilter } from '~/utils/nflPositions'
import { groupNflPropRows } from '~/utils/nflPropRows'
import { playerSelected, teamMatches } from '~/utils/propFilters'
import { isTargetsReference } from '~/utils/nflTargets'

/** A slate line carrying the game it came from, so the board can show a matchup without regrouping. */
export interface NflBoardLine extends NflSlateLine {
  gameId: number
  awayTeam: string
  homeTeam: string
  startUtc: string | null
}

export interface NflBoardCategory {
  market: string
  /** Default rows: v4 comparisons or Rec Targets references. */
  rateable: NflBoardLine[]
  /** Alternate payouts, partial segments, or thin samples. */
  other: NflBoardLine[]
  /** Median rateable line, the shared denominator every row in this category is scored against. */
  referenceLine: number | null
}

const OUT_FLAG = 'injury_out'
const DOUBTFUL_FLAG = 'injury_doubtful'

/**
 * Ranking by edge share floats minimum-sample rows to the top, because a thin baseline
 * produces the most extreme average: a backup quarterback's four mop-up games read as a
 * 66% miss on a starter's line. Rows below this sit under the full-sample ones. Matches the
 * confidence cut `/nfl/projections` already uses in `api/app/routers/nfl.py`.
 */
export const CONFIDENT_SAMPLE_GAMES = 8

export function flattenSlateLines(games: NflSlateGame[]): NflBoardLine[] {
  return games.flatMap(game => game.lines.map(line => ({
    ...line,
    gameId: game.gameId,
    awayTeam: game.awayTeam,
    homeTeam: game.homeTeam,
    startUtc: game.startUtc,
  })))
}

export interface NflFilteredCategory {
  category: NflBoardCategory
  rateable: NflBoardLine[]
  other: NflBoardLine[]
}

/** Slate lines store only the opponent, so the player's team is the game's other side. */
export function nflLineTeam(line: Pick<NflBoardLine, 'opponentTeam' | 'awayTeam' | 'homeTeam'>): string | null {
  if (line.opponentTeam === line.homeTeam) return line.awayTeam
  if (line.opponentTeam === line.awayTeam) return line.homeTeam
  return null
}

/** A board is actionable only until kickoff; an unknown kickoff stays visible. */
export function isUpcomingGame(game: Pick<NflSlateGame, 'startUtc'>, now = new Date()): boolean {
  if (game.startUtc === null) return true
  const kickoff = Date.parse(game.startUtc)
  return Number.isNaN(kickoff) || kickoff > now.getTime()
}

/** An empty list means every game. */
export function filterNflPropBoardGames(games: NflSlateGame[], gameIds: readonly number[], now = new Date()): NflSlateGame[] {
  return games.filter(game => game.lines.length > 0
    && isUpcomingGame(game, now)
    && (gameIds.length === 0 || gameIds.includes(game.gameId)))
}

/**
 * The denominator every row in a category is scored against: the median rateable line.
 * Dividing by a row's own line looks right until the tail arrives - a blocking tight end
 * carries a 0.5-yard receiving line, and a routine 12-yard projection on it reads as
 * +2314%, taking the top of a board whose median line is 26.5. One shared denominator
 * keeps rows comparable and immune to a tiny one.
 */
export function categoryReferenceLine(lines: Pick<NflSlateLine, 'line'>[]): number | null {
  const values = lines.map(item => item.line).filter((value): value is number => value !== null && value > 0).sort((a, b) => a - b)
  if (!values.length) return null
  const middle = Math.floor(values.length / 2)
  return values.length % 2 ? values[middle] : (values[middle - 1] + values[middle]) / 2
}

/** Edge as a share of a typical line in the category, so markets of different scales rank alike. */
export function edgeShare(line: Pick<NflSlateLine, 'edge'>, referenceLine: number | null): number | null {
  if (line.edge === null || referenceLine === null || referenceLine === 0) return null
  return line.edge / referenceLine
}

/**
 * Mirrors v4's `edge_is_comparable`; Rec Targets follows its own reference path.
 * Anytime TD is never rateable until build-plan item 25c, so it shows only under "show all".
 */
export function isRateable(line: Pick<NflSlateLine, 'edge' | 'gamesInSample' | 'line' | 'market' | 'oddsType' | 'segment'>): boolean {
  return line.market !== 'anytime_touchdown'
    && !isTargetsReference(line.market)
    && line.edge !== null
    && line.line !== null
    && line.oddsType === 'standard'
    && line.segment === 'full_game'
    && line.gamesInSample >= MIN_BASELINE_GAMES
}

/** A ruled-out player must never top a category, whatever the kickoff or edge. */
function availabilityTier(line: Pick<NflSlateLine, 'qualityFlags'>): number {
  if (line.qualityFlags.includes(OUT_FLAG)) return 2
  if (line.qualityFlags.includes(DOUBTFUL_FLAG)) return 1
  return 0
}

type BoardOrderLine = Pick<NflBoardLine, 'lineId' | 'playerName' | 'qualityFlags' | 'startUtc'>

export function isConfidentSample(line: Pick<NflBoardLine, 'gamesInSample'>): boolean {
  return line.gamesInSample >= CONFIDENT_SAMPLE_GAMES
}

/** The tiers a line is ranked by before edge size: available, then a confident sample, then a current season. */
export function compareBoardTiers(left: Pick<NflBoardLine, 'gamesInSample' | 'qualityFlags'>, right: Pick<NflBoardLine, 'gamesInSample' | 'qualityFlags'>): number {
  const availability = availabilityTier(left) - availabilityTier(right)
  if (availability) return availability

  const sample = Number(isConfidentSample(right)) - Number(isConfidentSample(left))
  if (sample) return sample

  return Number(left.qualityFlags.includes(STALE_FLAG)) - Number(right.qualityFlags.includes(STALE_FLAG))
}

function kickoffMs(startUtc: string | null): number {
  const kickoff = startUtc === null ? Number.NaN : Date.parse(startUtc)
  return Number.isNaN(kickoff) ? Number.POSITIVE_INFINITY : kickoff
}

/**
 * Board order for every NFL market: availability, kickoff, then player. No slice is adopted
 * (27h), so the order never uses the gap, its direction or a probability.
 */
export function compareNflPropRows(left: BoardOrderLine, right: BoardOrderLine): number {
  const availability = availabilityTier(left) - availabilityTier(right)
  if (availability) return availability

  const leftKickoff = kickoffMs(left.startUtc)
  const rightKickoff = kickoffMs(right.startUtc)
  if (leftKickoff !== rightKickoff) return leftKickoff < rightKickoff ? -1 : 1

  return left.playerName.localeCompare(right.playerName) || left.lineId - right.lineId
}

/**
 * One bucket per market across every game in the week. Category order follows
 * `MARKET_LABELS` so the tab strip does not reshuffle as lines arrive.
 */
export function buildNflPropBoard(games: NflSlateGame[], position: NflPositionFilter, now = new Date()): NflBoardCategory[] {
  const rows = groupNflPropRows(filterNflSlateLinesByPosition(flattenSlateLines(filterNflPropBoardGames(games, [], now)), position))
  const byMarket = new Map<string, NflBoardLine[]>()
  for (const { primary } of rows) {
    byMarket.set(primary.market, [...(byMarket.get(primary.market) ?? []), primary])
  }

  const known = Object.keys(MARKET_LABELS).filter(market => byMarket.has(market))
  const unknown = [...byMarket.keys()].filter(market => !(market in MARKET_LABELS)).sort()

  return [...known, ...unknown].map(market => {
    const lines = byMarket.get(market) ?? []
    const primary = (line: NflBoardLine) => isTargetsReference(market)
      ? line.segment === 'full_game' && line.oddsType === 'standard'
      : isRateable(line)
    const rateable = lines.filter(primary)
    // A category with nothing rateable still needs a denominator for its "show all" rows.
    const referenceLine = categoryReferenceLine(rateable.length ? rateable : lines)
    return {
      market,
      referenceLine,
      rateable: rateable.sort(compareNflPropRows),
      other: lines.filter(line => !primary(line)).sort(compareNflPropRows),
    }
  })
}

/** Narrows rows only; the category keeps its unfiltered reference line, so a gap share never moves with a filter. */
export function filterNflBoardCategories(categories: NflBoardCategory[], players: readonly string[], team: string): NflFilteredCategory[] {
  const keep = (row: NflBoardLine) => playerSelected(row.playerName, players) && teamMatches(nflLineTeam(row), team)
  return categories.map(category => ({
    category,
    rateable: category.rateable.filter(keep),
    other: category.other.filter(keep),
  }))
}
