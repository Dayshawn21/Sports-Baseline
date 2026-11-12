import type { MatchBestPicks, MatchPrediction, PropLine } from '~/types/tennis'
import { playerOptions, playerSelected, withPropListFilters } from '~/utils/propFilters'

export type TennisPropSource = 'all' | 'prizepicks' | 'dk' | 'market' | 'model'
export type TennisTourFilter = 'all' | 'atp' | 'wta' | 'challenger' | 'wta_125'

export interface TennisBoardLine extends PropLine {
  matchup: string | null
  tournament: string | null
  tour: string | null
  bestOf: number | null
  reason?: string | null
}

export interface TennisBoardCategory {
  market: string
  label: string
  rateable: TennisBoardLine[]
  other: TennisBoardLine[]
}

export const TENNIS_PROP_SOURCES: Array<{ value: TennisPropSource, label: string }> = [
  { value: 'all', label: 'All' },
  { value: 'prizepicks', label: 'PrizePicks' },
  { value: 'dk', label: 'DraftKings' },
  { value: 'market', label: 'Market odds' },
  { value: 'model', label: 'Model only' },
]

export const TENNIS_TOUR_FILTERS: Array<{ value: TennisTourFilter, label: string }> = [
  { value: 'all', label: 'All tours' },
  { value: 'atp', label: 'ATP' },
  { value: 'wta', label: 'WTA' },
  { value: 'challenger', label: 'Challenger' },
  { value: 'wta_125', label: 'WTA 125' },
]

export type TennisSurfaceFilter = 'all' | 'hard' | 'clay' | 'grass'
export type TennisBestOfFilter = 'all' | '3' | '5'
/** `default` is today's board: standard and demon lines, goblins hidden unless adopted. */
export type TennisLineTypeFilter = 'default' | 'standard' | 'demon' | 'goblin'

export interface TennisContextFilter {
  surface: TennisSurfaceFilter
  bestOf: TennisBestOfFilter
  tour: TennisTourFilter
  lineType: TennisLineTypeFilter
}

export const DEFAULT_TENNIS_CONTEXT_FILTER: TennisContextFilter = { surface: 'all', bestOf: 'all', tour: 'all', lineType: 'default' }

export const TENNIS_SURFACE_FILTERS: Array<{ value: TennisSurfaceFilter, label: string }> = [
  { value: 'all', label: 'All surfaces' },
  { value: 'hard', label: 'Hard' },
  { value: 'clay', label: 'Clay' },
  { value: 'grass', label: 'Grass' },
]

export const TENNIS_BEST_OF_FILTERS: Array<{ value: TennisBestOfFilter, label: string }> = [
  { value: 'all', label: 'Any format' },
  { value: '3', label: 'Best of 3' },
  { value: '5', label: 'Best of 5' },
]

export const TENNIS_LINE_TYPE_FILTERS: Array<{ value: TennisLineTypeFilter, label: string }> = [
  { value: 'default', label: 'Standard + demon' },
  { value: 'standard', label: 'Standard' },
  { value: 'demon', label: 'Demon' },
  { value: 'goblin', label: 'Goblin' },
]

const CONTEXT_PARAMS = { surface: 'surface', bestOf: 'bo', tour: 'tour', lineType: 'line' } as const

function parseOption<T extends string>(value: string | null, options: ReadonlyArray<{ value: T }>, fallback: T): T {
  return options.find(option => option.value === value)?.value ?? fallback
}

/** An unknown value, as from an old or edited link, reads as that filter's default. */
export function parseTennisContextFilter(params: URLSearchParams): TennisContextFilter {
  return {
    surface: parseOption(params.get(CONTEXT_PARAMS.surface), TENNIS_SURFACE_FILTERS, 'all'),
    bestOf: parseOption(params.get(CONTEXT_PARAMS.bestOf), TENNIS_BEST_OF_FILTERS, 'all'),
    tour: parseOption(params.get(CONTEXT_PARAMS.tour), TENNIS_TOUR_FILTERS, 'all'),
    lineType: parseOption(params.get(CONTEXT_PARAMS.lineType), TENNIS_LINE_TYPE_FILTERS, 'default'),
  }
}

/** Writes each filter that differs from its default and leaves every other param alone. */
export function withTennisContextFilter(params: URLSearchParams, filter: TennisContextFilter): URLSearchParams {
  const next = new URLSearchParams(params)
  for (const key of Object.keys(CONTEXT_PARAMS) as Array<keyof TennisContextFilter>) {
    if (filter[key] === DEFAULT_TENNIS_CONTEXT_FILTER[key]) next.delete(CONTEXT_PARAMS[key])
    else next.set(CONTEXT_PARAMS[key], filter[key])
  }
  return next
}

/** Line type is a PrizePicks payout tier, so it applies only while PrizePicks rows can show. */
export function lineTypeApplies(source: TennisPropSource): boolean {
  return source === 'all' || source === 'prizepicks'
}

/** A null surface or format passes only "all"; a row with no PrizePicks tier passes only the default line type. */
export function tennisContextMatches(line: TennisBoardLine, filter: TennisContextFilter): boolean {
  return (filter.surface === 'all' || normalized(line.surface) === filter.surface)
    && (filter.bestOf === 'all' || line.bestOf === Number(filter.bestOf))
    && tourMatches(line, filter.tour)
    && (filter.lineType === 'default' || payoutTier(line) === filter.lineType)
}

const MARKET_LABELS: Record<string, string> = {
  aces: 'Aces',
  double_faults: 'Double faults',
  total_games: 'Total games',
  '1st_set_total_games': '1st set games',
  '1st_set_total_games_won': '1st set games won',
  break_points: 'Break points',
  break_points_converted: 'Break points converted',
  break_points_won: 'Break points won',
  fantasy_score: 'Fantasy score',
  game_spread: 'Game spread',
  moneyline: 'Moneyline',
  win_a_set: 'Win a Set',
  set1_winner: 'First-set winner',
  set_handicap: 'Set handicap',
  total_sets: 'Total sets',
  total_tie_breaks: 'Total tie breaks',
  unforced_errors: 'Unforced errors',
  winners: 'Winners',
}

const BLOCKING_FLAGS = new Set([
  'missing_player', 'missing_match', 'missing_stats', 'unsupported_stat', 'bo5_unsupported_stat',
  'stale_stats', 'stale_odds', 'small_sample', 'missing_prediction',
  'match_finished', 'match_link_invalid', 'ungraded_stat',
])

function numeric(value: string | number | null | undefined): number | null {
  if (value == null || value === '') return null
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : null
}

function normalized(value: string | null | undefined): string {
  return (value ?? '').trim().toLowerCase().replace(/[\s-]+/g, '_')
}

/** The category key a stat type has on the board, and so in `?market=` on the match and player pages. */
export function marketKey(statType: string): string {
  return normalized(statType)
}

function sourceMatches(line: PropLine, source: TennisPropSource): boolean {
  return source === 'all' || sourceKey(line.source) === source
}

function tourMatches(line: TennisBoardLine, tour: TennisTourFilter): boolean {
  if (tour === 'all') return true
  const value = normalized(line.tour)
  if (tour === 'wta_125') return value.includes('wta_125') || value.includes('wta125')
  if (tour === 'challenger') return value.includes('challenger') && !value.includes('wta_125') && !value.includes('wta125')
  return value === tour
}

function sourceKey(source: string): TennisPropSource {
  const value = source.toLowerCase()
  if (value === 'prizepicks') return 'prizepicks'
  if (value === 'draftkings' || value === 'dk') return 'dk'
  if (value === 'model') return 'model'
  return 'market'
}

function findPrediction(line: PropLine, predictions: MatchPrediction[]): MatchPrediction | null {
  if (line.matchId != null) return predictions.find(item => item.matchId === line.matchId) ?? null
  const player = normalized(line.playerName)
  if (!player) return null
  return predictions.find(item => normalized(item.p1Name) === player || normalized(item.p2Name) === player) ?? null
}

export function marketLabel(market: string): string {
  return MARKET_LABELS[normalized(market)] ?? market.replaceAll('_', ' ')
}

/** marketLabel for a table cell or heading: capitalized, including stats it has no label for. */
export function marketTitle(market: string): string {
  const label = marketLabel(market)
  return label.charAt(0).toUpperCase() + label.slice(1)
}

export function sourceLabel(source: string): string {
  return TENNIS_PROP_SOURCES.find(item => item.value === sourceKey(source))?.label ?? source
}

export function lineNumber(line: Pick<PropLine, 'line'>): number | null {
  return numeric(line.line)
}

export function isMoneyline(line: Pick<PropLine, 'statType'>): boolean {
  return normalized(line.statType) === 'moneyline'
}

export function isWinASet(line: Pick<PropLine, 'statType'>): boolean {
  return normalized(line.statType) === 'win_a_set'
}

/** Goblins are over-only alternate lines, intentionally omitted from the board. */
export function isGoblin(line: Pick<PropLine, 'oddsType'>): boolean {
  return normalized(line.oddsType) === 'goblin'
}

/** PrizePicks payout tier; other sources carry real prices, so they get none. */
export function payoutTier(line: Pick<PropLine, 'oddsType' | 'source'>): 'standard' | 'demon' | 'goblin' | null {
  if (sourceKey(line.source) !== 'prizepicks') return null
  const tier = normalized(line.oddsType)
  if (tier === 'demon' || tier === 'goblin') return tier
  return 'standard'
}

export function winASetStrength(modelProbability: number | null | undefined): 'LOCK' | 'STRONG' | null {
  if (modelProbability == null) return null
  if (modelProbability >= 0.70) return 'LOCK'
  if (modelProbability >= 0.62) return 'STRONG'
  return null
}

function americanImpliedProbability(odds: number): number {
  return odds > 0 ? 100 / (odds + 100) : Math.abs(odds) / (Math.abs(odds) + 100)
}

/** The two sides' win probabilities with the book's margin removed, from their American prices. */
export function marketWinProbabilities(p1Odds: number, p2Odds: number): [number, number] {
  const p1Raw = americanImpliedProbability(p1Odds)
  const p2Raw = americanImpliedProbability(p2Odds)
  const denominator = p1Raw + p2Raw
  return [p1Raw / denominator, p2Raw / denominator]
}

/**
 * Turns existing match predictions into side-specific board rows without adding a new API.
 * Reference only: tennis moneyline picks are off since 26d (MONEYLINE_PICKS_ENABLED in
 * best_picks.py), so a row carries no recommendation, tier or EV, as on the match page.
 */
export function moneylineBoardRows(predictions: MatchPrediction[]): PropLine[] {
  return predictions.flatMap(match => {
    if (match.p1WinProb == null || match.p2WinProb == null || match.p1OddsAmerican == null || match.p2OddsAmerican == null) return []
    const [p1Market, p2Market] = marketWinProbabilities(match.p1OddsAmerican, match.p2OddsAmerican)
    const sides = [
      { playerName: match.p1Name, modelProb: match.p1WinProb, odds: match.p1OddsAmerican, marketProb: p1Market, id: -(match.matchId * 2 + 1) },
      { playerName: match.p2Name, modelProb: match.p2WinProb, odds: match.p2OddsAmerican, marketProb: p2Market, id: -(match.matchId * 2 + 2) },
    ]
    return sides.map(side => ({
      id: side.id,
      playerId: null,
      playerName: side.playerName,
      matchId: match.matchId,
      source: 'market',
      statType: 'moneyline',
      line: String(side.odds),
      oddsType: 'standard',
      fetchedAt: match.startUtc ?? new Date(0).toISOString(),
      startTime: match.startUtc,
      p1Odds: side.odds,
      p2Odds: null,
      pOver: null,
      pUnder: null,
      confidence: null,
      recommendation: null,
      statAvg: side.modelProb * 100,
      // Relative edge, the same definition the backend's moneyline pick uses.
      edgePct: (side.modelProb - side.marketProb) / side.marketProb * 100,
      evPct: null,
      hitProbability: side.modelProb,
      breakEvenPct: side.marketProb * 100,
      matchesCount: null,
      surface: match.surface,
      projectionSource: 'ensemble',
      projectionInputs: { model_probability: side.modelProb, market_probability: side.marketProb },
      dataQualityFlags: match.qualityFlags,
      projectionStatus: 'ok',
      audit: null,
    }))
  })
}

/** Reuses the existing unpriced derived pick, without representing it as a priced edge. */
export function winASetBoardRows(matches: MatchBestPicks[]): PropLine[] {
  return matches.flatMap(match => match.picks.flatMap((pick, index) => {
      if (pick.pickType !== 'derived' || pick.label !== 'Win a Set' || pick.oddsSource !== 'unpriced' || pick.modelProb == null) return []
      const modelProb = pick.modelProb
      const strength = winASetStrength(modelProb)
      return {
        id: -(match.matchId * 10 + index + 3),
        playerId: null,
        playerName: pick.playerName,
        matchId: match.matchId,
        source: 'model',
        statType: 'win_a_set',
        line: null,
        oddsType: 'unpriced',
        fetchedAt: match.startUtc ?? new Date(0).toISOString(),
        startTime: match.startUtc,
        pOver: null,
        pUnder: null,
        confidence: strength ?? pick.confidence,
        recommendation: null,
        statAvg: modelProb * 100,
        edgePct: pick.edgePct,
        evPct: null,
        hitProbability: modelProb,
        breakEvenPct: null,
        matchesCount: null,
        surface: match.surface,
        projectionSource: 'match_model',
        projectionInputs: { model_probability: modelProb, source: 'unpriced derived pick' },
        dataQualityFlags: pick.dataQualityFlags ?? [],
        projectionStatus: 'unpriced',
        audit: null,
        reason: pick.reasoning,
      }
    }))
}

/** A line with a complete, unblocked projection. Rated, never ranked: tennis props carry no tier (48f). */
export function isTennisRateable(line: PropLine): boolean {
  const status = line.projectionStatus ?? 'ok'
  const flags = line.dataQualityFlags ?? []
  return !isMoneyline(line)
    && line.recommendation != null
    && line.statAvg != null
    && line.pOver != null
    && numeric(line.line) != null
    && status === 'ok'
    && !flags.some(flag => BLOCKING_FLAGS.has(flag))
    && line.audit?.matchLinked !== false
}

/** True only on a line 48e's forward check adopted; nothing else is ranked or colored. */
export function isAdopted(line: Pick<PropLine, 'adoptedPick'>): boolean {
  return line.adoptedPick != null
}

export function trustLabel(line: PropLine): string {
  if (isAdopted(line)) return 'Pick'
  return isTennisRateable(line) ? 'Reference' : 'Review'
}

export function signalSummary(line: PropLine): string {
  if ('reason' in line && typeof line.reason === 'string') return line.reason
  if (isMoneyline(line)) return 'Reference only: tennis moneyline picks are off'
  if (line.statsStale) return 'Rolling stats need refresh'
  if (line.dataQualityFlags?.includes('small_sample')) return 'Thin rolling sample'
  const lineValue = numeric(line.line)
  if (!isMoneyline(line) && line.statAvg != null && lineValue != null && line.recommendation) {
    const opponent = line.opponentStatAvg != null ? ` Opponent allows ${line.opponentStatAvg.toFixed(1)}.` : ''
    const ungraded = line.dataQualityFlags?.includes('ungraded_stat') ? 'New stat, not yet graded. ' : ''
    return `${ungraded}Model projects ${line.statAvg.toFixed(1)} vs the ${lineValue.toFixed(1)} line.${opponent}`
  }
  if (line.opponentStatAvg != null) return `Opponent allows ${line.opponentStatAvg.toFixed(1)}`
  if (line.matchesCount != null) return `${line.matchesCount}-match rolling sample`
  return line.recommendation ? 'Model context is limited' : 'Model score unavailable'
}

function startMs(line: Pick<PropLine, 'startTime'>): number {
  const time = line.startTime ? Date.parse(line.startTime) : Number.NaN
  return Number.isNaN(time) ? Number.POSITIVE_INFINITY : time
}

// Only adopted lines are ranked, by margin over break-even (48g). Every other
// line reads in start order, never by EV or probability. Win a Set is a
// derived match angle and keeps its order.
export function compareLines(left: PropLine, right: PropLine): number {
  const leftMargin = left.adoptedPick?.margin
  const rightMargin = right.adoptedPick?.margin
  if (leftMargin != null || rightMargin != null) {
    if (leftMargin == null) return 1
    if (rightMargin == null) return -1
    if (rightMargin !== leftMargin) return rightMargin - leftMargin
  }
  if (isWinASet(left) && isWinASet(right)) {
    const probability = (right.hitProbability ?? Number.NEGATIVE_INFINITY) - (left.hitProbability ?? Number.NEGATIVE_INFINITY)
    if (probability !== 0) return probability
  }
  const start = startMs(left) - startMs(right)
  if (start !== 0 && !Number.isNaN(start)) return start
  return (left.playerName ?? '').localeCompare(right.playerName ?? '')
    || left.statType.localeCompare(right.statType)
    || left.id - right.id
}

export function enrichTennisPropLines(props: PropLine[], predictions: MatchPrediction[], source: TennisPropSource, includeAlternates = false): TennisBoardLine[] {
  return props.filter(line => sourceMatches(line, source) && (includeAlternates || !isGoblin(line) || isAdopted(line))).map(line => {
    const match = findPrediction(line, predictions)
    const opponent = match && normalized(match.p1Name) === normalized(line.playerName)
      ? match.p2Name
      : match && normalized(match.p2Name) === normalized(line.playerName)
        ? match.p1Name
        : null
    return {
      ...line,
      matchup: opponent ? `${line.playerName} vs ${opponent}` : match ? `${match.p1Name} vs ${match.p2Name}` : null,
      tournament: match?.tournament ?? null,
      tour: match?.tourLabel ?? match?.tour ?? null,
      surface: line.surface ?? match?.surface ?? null,
      bestOf: line.bestOf ?? match?.bestOf ?? null,
      startTime: line.startTime ?? match?.startUtc ?? null,
    }
  })
}

// An adopted goblin is a pick, so it leaves the alternates bucket.
function isBoardRateable(line: PropLine): boolean {
  return isAdopted(line) || (!isGoblin(line) && isTennisRateable(line))
}

export function buildTennisPropBoard(
  props: PropLine[], predictions: MatchPrediction[], source: TennisPropSource,
  filter: TennisContextFilter = DEFAULT_TENNIS_CONTEXT_FILTER, includeAlternates = false,
): TennisBoardCategory[] {
  const byMarket = new Map<string, TennisBoardLine[]>()
  const lines = enrichTennisPropLines(props, predictions, source, includeAlternates || filter.lineType === 'goblin')
  for (const line of lines.filter(line => tennisContextMatches(line, filter))) {
    const market = normalized(line.statType)
    byMarket.set(market, [...(byMarket.get(market) ?? []), line])
  }
  return [...byMarket.entries()]
    .sort(([left], [right]) => marketLabel(left).localeCompare(marketLabel(right)))
    .map(([market, lines]) => ({
      market,
      label: marketLabel(market),
      rateable: lines.filter(isBoardRateable).sort(compareLines),
      other: lines.filter(line => !isBoardRateable(line)).sort(compareLines),
    }))
}

/** Every market stays, emptied ones included, so the pills do not reshuffle as a selection narrows them. */
export function filterTennisBoardCategories(categories: TennisBoardCategory[], players: readonly string[]): TennisBoardCategory[] {
  if (players.length === 0) return categories
  const keep = (line: TennisBoardLine) => playerSelected(line.playerName, players)
  return categories.map(category => ({ ...category, rateable: category.rateable.filter(keep), other: category.other.filter(keep) }))
}

export function tennisBoardPath(players: readonly string[], filter: TennisContextFilter = DEFAULT_TENNIS_CONTEXT_FILTER): string {
  const search = withTennisContextFilter(withPropListFilters(new URLSearchParams(), { player: players }), filter).toString()
  return search === '' ? '/tennis/props' : `/tennis/props?${search}`
}

export function tennisPlayerOptions(categories: TennisBoardCategory[], players: readonly string[]): string[] {
  return playerOptions(categories.flatMap(category => [...category.rateable, ...category.other].map(line => line.playerName)), players)
}
