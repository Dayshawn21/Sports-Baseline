import type { NflSlateGame, NflSlateLine } from '~/types/nfl'
import { MIN_BASELINE_GAMES, STALE_FLAG } from '~/utils/nflBaseline'
import { MARKET_LABELS } from '~/utils/nflLabels'
import { filterNflSlateLinesByPosition, type NflPositionFilter } from '~/utils/nflPositions'
import { groupNflPropRows } from '~/utils/nflPropRows'
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
  /** Default rows: ranked v4 comparisons or unranked Rec Targets references. */
  rateable: NflBoardLine[]
  /** Ranked, but alternate payouts, partial segments, or thin samples. */
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

/** A board is actionable only until kickoff; an unknown kickoff stays visible. */
export function isUpcomingGame(game: Pick<NflSlateGame, 'startUtc'>, now = new Date()): boolean {
  if (game.startUtc === null) return true
  const kickoff = Date.parse(game.startUtc)
  return Number.isNaN(kickoff) || kickoff > now.getTime()
}

export function filterNflPropBoardGames(games: NflSlateGame[], gameId: number | null, now = new Date()): NflSlateGame[] {
  return games.filter(game => game.lines.length > 0
    && isUpcomingGame(game, now)
    && (gameId === null || game.gameId === gameId))
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
 * Mirrors v4's `edge_is_comparable`; Rec Targets follows its own unranked reference path.
 * Anytime TD is never rateable until build-plan item 25c, so it ranks by probability under
 * "show all" without a pick.
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

/** A ruled-out player must never top a category, however large the edge looks. */
function availabilityTier(line: Pick<NflSlateLine, 'qualityFlags'>): number {
  if (line.qualityFlags.includes(OUT_FLAG)) return 2
  if (line.qualityFlags.includes(DOUBTFUL_FLAG)) return 1
  return 0
}

type RankedLine = Pick<NflBoardLine, 'edge' | 'gamesInSample' | 'line' | 'lineId' | 'playerName' | 'qualityFlags'>
type AnytimeTdRankedLine = Pick<NflBoardLine, 'lineId' | 'playerName' | 'projection'>

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

/** Ranks one category, so every row is scored against that category's own reference line. */
export function compareBoardLines(referenceLine: number | null) {
  return (left: RankedLine, right: RankedLine): number => {
    const tier = compareBoardTiers(left, right)
    if (tier) return tier

    const magnitude = Math.abs(edgeShare(right, referenceLine) ?? 0) - Math.abs(edgeShare(left, referenceLine) ?? 0)
    if (magnitude) return magnitude

    return left.playerName.localeCompare(right.playerName) || left.lineId - right.lineId
  }
}

/** Anytime TD uses a probability model, so its board ranks by that model rather than raw edge. */
export function compareAnytimeTdLines(left: AnytimeTdRankedLine, right: AnytimeTdRankedLine): number {
  const probability = (right.projection ?? Number.NEGATIVE_INFINITY) - (left.projection ?? Number.NEGATIVE_INFINITY)
  if (probability) return probability
  return left.playerName.localeCompare(right.playerName) || left.lineId - right.lineId
}

/**
 * One ranked bucket per market across every game in the week. Category order follows
 * `MARKET_LABELS` so the tab strip does not reshuffle as lines arrive.
 */
export function buildNflPropBoard(games: NflSlateGame[], position: NflPositionFilter, now = new Date()): NflBoardCategory[] {
  const rows = groupNflPropRows(filterNflSlateLinesByPosition(flattenSlateLines(filterNflPropBoardGames(games, null, now)), position))
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
    const compare = isTargetsReference(market)
      ? (left: NflBoardLine, right: NflBoardLine) => left.playerName.localeCompare(right.playerName) || left.lineId - right.lineId
      : market === 'anytime_touchdown'
      ? compareAnytimeTdLines
      : compareBoardLines(referenceLine)
    return {
      market,
      referenceLine,
      rateable: rateable.sort(compare),
      other: lines.filter(line => !primary(line)).sort(compare),
    }
  })
}
