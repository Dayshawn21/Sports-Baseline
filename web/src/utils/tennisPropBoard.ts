import type { MatchBestPicks, MatchPrediction, PropLine } from '~/types/tennis'

export type TennisPropSource = 'all' | 'prizepicks' | 'dk' | 'bet' | 'market' | 'model'
export type TennisTourFilter = 'all' | 'atp' | 'wta' | 'challenger' | 'wta_125'

export interface TennisBoardLine extends PropLine {
  matchup: string | null
  tournament: string | null
  tour: string | null
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
  { value: 'bet', label: 'Bet365' },
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
  'missing_player', 'missing_match', 'missing_stats', 'unsupported_stat',
  'stale_stats', 'stale_odds', 'market_stale', 'small_sample', 'missing_prediction', 'missing_projection',
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
  if (value === 'market') return 'market'
  if (value === 'model') return 'model'
  return 'bet'
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

/**
 * Turns existing match predictions into side-specific board rows without adding a new API.
 * Reference only: tennis moneyline picks are off since 26d (MONEYLINE_PICKS_ENABLED in
 * best_picks.py), so a row carries no recommendation, tier or EV, as on the match page.
 */
export function moneylineBoardRows(predictions: MatchPrediction[]): PropLine[] {
  return predictions.flatMap(match => {
    if (match.p1WinProb == null || match.p2WinProb == null || match.p1OddsAmerican == null || match.p2OddsAmerican == null) return []
    const p1Raw = americanImpliedProbability(match.p1OddsAmerican)
    const p2Raw = americanImpliedProbability(match.p2OddsAmerican)
    const denominator = p1Raw + p2Raw
    const sides = [
      { playerName: match.p1Name, modelProb: match.p1WinProb, odds: match.p1OddsAmerican, marketProb: p1Raw / denominator, id: -(match.matchId * 2 + 1) },
      { playerName: match.p2Name, modelProb: match.p2WinProb, odds: match.p2OddsAmerican, marketProb: p2Raw / denominator, id: -(match.matchId * 2 + 2) },
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

export function isTennisRateable(line: PropLine): boolean {
  const status = line.projectionStatus ?? 'ok'
  const flags = line.dataQualityFlags ?? []
  return !isMoneyline(line)
    && line.recommendation != null
    && line.statAvg != null
    && line.evPct != null
    && line.evPct > 0
    && numeric(line.line) != null
    && status === 'ok'
    && !flags.some(flag => BLOCKING_FLAGS.has(flag))
    && line.audit?.matchLinked !== false
}

export function trustLabel(line: PropLine): string {
  if (!isTennisRateable(line)) return 'Review'
  if (line.confidence === 'LOCK' || line.confidence === 'STRONG') return 'Ready'
  return 'Lean'
}

export function signalSummary(line: PropLine): string {
  if ('reason' in line && typeof line.reason === 'string') return line.reason
  if (isMoneyline(line)) return 'Reference only: tennis moneyline picks are off'
  if (line.statsStale) return 'Rolling stats need refresh'
  if (line.dataQualityFlags?.includes('small_sample')) return 'Thin rolling sample'
  const lineValue = numeric(line.line)
  if (!isMoneyline(line) && line.statAvg != null && lineValue != null && line.recommendation) {
    const pick = line.recommendation.toUpperCase() === 'UNDER' ? 'Under' : 'Over'
    const opponent = line.opponentStatAvg != null ? ` Opponent allows ${line.opponentStatAvg.toFixed(1)}.` : ''
    const ungraded = line.dataQualityFlags?.includes('ungraded_stat') ? 'New stat, not yet graded. ' : ''
    return `${ungraded}Model projects ${line.statAvg.toFixed(1)} vs the ${lineValue.toFixed(1)} line (${pick}).${opponent}`
  }
  if (line.opponentStatAvg != null) return `Opponent allows ${line.opponentStatAvg.toFixed(1)}`
  if (line.matchesCount != null) return `${line.matchesCount}-match rolling sample`
  return line.recommendation ? 'Model context is limited' : 'Model score unavailable'
}

const CONFIDENCE_RANK: Record<string, number> = { LOCK: 0, STRONG: 1, LEAN: 2 }

function confidenceRank(line: TennisBoardLine): number {
  return CONFIDENCE_RANK[(line.confidence ?? '').toUpperCase()] ?? 3
}

// Highest EV first with its sign, so a -30% line never outranks a +5% one;
// unpriced lines go last.
function compareEv(left: number | null | undefined, right: number | null | undefined): number {
  if (left == null || right == null) return (left == null ? 1 : 0) - (right == null ? 1 : 0)
  return right - left
}

// Tier before EV: the tiers carry a hit-probability floor, so a high-EV coin-flip
// demon cannot outrank a reliable standard pick.
function compareLines(left: TennisBoardLine, right: TennisBoardLine): number {
  if (isWinASet(left) && isWinASet(right)) {
    const probability = (right.hitProbability ?? Number.NEGATIVE_INFINITY) - (left.hitProbability ?? Number.NEGATIVE_INFINITY)
    if (probability !== 0) return probability
  }
  const tier = confidenceRank(left) - confidenceRank(right)
  if (tier !== 0) return tier
  const ev = compareEv(left.evPct, right.evPct)
  if (ev !== 0) return ev
  return (left.playerName ?? '').localeCompare(right.playerName ?? '') || left.id - right.id
}

export function enrichTennisPropLines(props: PropLine[], predictions: MatchPrediction[], source: TennisPropSource): TennisBoardLine[] {
  return props.filter(line => sourceMatches(line, source) && !isGoblin(line)).map(line => {
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
      startTime: line.startTime ?? match?.startUtc ?? null,
    }
  })
}

export function buildTennisPropBoard(
  props: PropLine[], predictions: MatchPrediction[], source: TennisPropSource, tour: TennisTourFilter = 'all',
): TennisBoardCategory[] {
  const byMarket = new Map<string, TennisBoardLine[]>()
  for (const line of enrichTennisPropLines(props, predictions, source).filter(line => tourMatches(line, tour))) {
    const market = normalized(line.statType)
    byMarket.set(market, [...(byMarket.get(market) ?? []), line])
  }
  return [...byMarket.entries()]
    .sort(([left], [right]) => marketLabel(left).localeCompare(marketLabel(right)))
    .map(([market, lines]) => ({
      market,
      label: marketLabel(market),
      rateable: lines.filter(isTennisRateable).sort(compareLines),
      other: lines.filter(line => !isTennisRateable(line)).sort(compareLines),
    }))
}
