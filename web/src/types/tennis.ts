// All TypeScript types for the Lineform API.
// Field names are camelCase — the FastAPI backend uses alias_generator=to_camel.

export interface MatchPrediction {
  matchId: number
  startUtc: string | null
  p1Name: string
  p2Name: string
  tour: string
  /** Display label for `tour` — WTA 125 draws arrive from the feed as CHALLENGER. */
  tourLabel?: string
  surface: string | null
  tournament: string | null
  round: string | null
  p1WinProb: number | null
  p2WinProb: number | null
  p1EloProb: number | null
  p1MlProb: number | null
  p1MarketProb: number | null
  ensembleWeights: Record<string, number>
  qualityFlags: string[]
  p1OddsAmerican: number | null
  p2OddsAmerican: number | null
  h2hP1Wins: number
  h2hP2Wins: number
  p1Id?: number | null
  p2Id?: number | null
}

export interface PredictionsResponse {
  date: string
  count: number
  matches: MatchPrediction[]
}

/** A line whose slice 48e's forward check adopted, so it is ranked and colored (48g). */
export interface AdoptedPick {
  side: 'over' | 'under'
  probability: number   // push-excluded P(side)
  breakEven: number
  margin: number        // probability - breakEven, the ranking key
  rule: string
  projectionVersion: string
}

export interface PropLine {
  id: number
  playerId: number | null
  playerName?: string | null
  matchId: number | null
  source: string
  statType: string
  line: string | null   // Decimal comes as string from JSON
  oddsType: string | null
  fetchedAt: string
  startTime: string | null
  p1Odds?: number | null
  p2Odds?: number | null
  pOver: number | null
  pUnder: number | null
  pPush?: number | null
  confidence: string | null
  recommendation?: string | null   // "OVER" | "UNDER"
  statAvg?: number | null          // projected per-match average from rolling stats
  edgePct?: number | null          // (statAvg - line) / line * 100 — projection delta, NOT a betting edge
  evPct?: number | null            // expected return %: hitProbability * decimal odds - 1
  hitProbability?: number | null   // model probability for the playable side
  breakEvenPct?: number | null     // hit rate this price needs to break even
  matchesCount?: number | null     // rolling stats sample size
  surface?: string | null          // match surface (Hard / Clay / Grass)
  marketTotalGames?: number | null       // market total used for match-length context
  expectedServicePoints?: number | null  // service-point volume used for serve props
  projectionSource?: 'market_total' | 'model_total' | string | null
  projectionInputs?: Record<string, number | string>
  opponentStatAvg?: number | null        // derived per-match figure opponent typically gives up
  opponentMatchesCount?: number | null   // opponent rolling stats sample size
  statsComputedAt?: string | null        // ISO timestamp of rolling stats freshness
  statsStale?: boolean | null            // true if stats older than freshness threshold
  dataQualityFlags?: string[]
  projectionStatus?: 'ok' | 'missing_player' | 'missing_match' | 'missing_stats' | 'unsupported_stat' | string
  audit?: {
    playerResolved: boolean
    matchLinked: boolean
    statsFresh: boolean | null
    sampleSize: number | null
    opponentStatsFound: boolean
    predictionFound: boolean
    projectionFound: boolean
    matchLinkMethod?: string | null
  } | null
  adoptedPick?: AdoptedPick | null
}

export interface PlayerStats {
  playerId: number
  surface: string | null
  statPeriod: string
  winRate: number | null
  svcPtsWon: number | null
  retPtsWon: number | null
  acesPerGame: number | null
  dfPerGame: number | null
  holdPct: number | null
  breakPct: number | null
  matchesCount: number | null
  firstInPct: number | null
  firstWonPct: number | null
  secondWonPct: number | null
  dominanceRatio: number | null
  breakPointsCreatedPerReturnGame?: number | null
  allowedBreakPointsPerServiceGame?: number | null
  // ELO ratings (all surfaces + per surface)
  elo: number | null
  eloHard: number | null
  eloClay: number | null
  eloGrass: number | null
}

export interface RecentMatchResult {
  matchDate: string
  opponentName: string
  score: string | null
  result: 'W' | 'L'
  aces: number | null
  doubleFaults: number | null
  breakChancesCreated: number | null
  breakPointsConverted: number | null
}

export interface PlayerFormStats {
  svcPtsWon: number | null
  retPtsWon: number | null
  acesPerGame: number | null
  dfPerGame: number | null
  holdPct: number | null
  breakPct: number | null
  winRate: number | null
}

export interface PlayerRecentForm {
  playerId: number
  playerName: string
  matches: RecentMatchResult[]
  last52W: PlayerFormStats | null
}

export interface MatchRecentFormResponse {
  matchId: number
  players: PlayerRecentForm[]
}

export interface MatchPlayerDetail {
  playerId: number
  name: string
  rank: number | null
  hand: 'R' | 'L' | null
  country: string | null
  elo: number | null
  eloSurface: number | null
}

export interface MatchH2H {
  p1Wins: number
  p2Wins: number
  surfaceP1Wins: number | null
  surfaceP2Wins: number | null
}

export interface MatchMeeting {
  matchDate: string
  tournament: string | null
  round: string | null
  surface: string | null
  /** Read from the winner's side; from p1's side when the winner is unknown. */
  score: string | null
  /** p1 or p2 of the match being viewed. */
  winnerSide: 'p1' | 'p2' | null
}

/** Load-bearing (32a): the player page links from it; later match-level features extend it. */
export interface MatchResearchStats {
  surface: string | null
  matchesCount: number | null
  computedAt: string | null
  winRate: number | null
  holdPct: number | null
  returnPointsWon: number | null
  breakConversionPct: number | null
  firstInPct: number | null
  firstServeWon: number | null
  secondServeWon: number | null
  firstReturnWon: number | null
  secondReturnWon: number | null
  thinSample: boolean
  statPeriod: string
  source: string
  snapshotBasis: string
}

export interface MatchWorkload {
  windowStart: string
  windowEndExclusive: string
  previousMatchDate: string | null
  calendarDaysSinceMatch: number | null
  matchesPlayed: number
  completedSets: number
  matchesWithCompleteScores: number
  minutesPlayed: number | null
  dateBasis: string
  historyLookbackDays: number
  source: string
}

export interface MatchResearch {
  players: Array<{
    playerId: number
    eloAsOfDate: string | null
    surfaceStats: MatchResearchStats | null
    overallStats: MatchResearchStats | null
    workload: MatchWorkload
  }>
  odds: Array<{ book: string; fetchedAt: string }>
  oddsCutoff: string
  eloSource: string
}

export interface MatchDetail {
  research?: MatchResearch | null
  matchId: number
  status: string
  startUtc: string | null
  tour: string
  tourLabel: string
  surface: string | null
  indoor: boolean | null
  tournament: string | null
  round: string | null
  bestOf: number
  score: string | null
  winnerSide: 'p1' | 'p2' | null
  p1: MatchPlayerDetail
  p2: MatchPlayerDetail
  h2h: MatchH2H
  /** Stored past meetings, newest first; can be fewer than the h2h count. */
  meetings: MatchMeeting[]
  prediction: MatchPrediction | null
  /** "live" for scheduled or live matches; "stored" is the last pre-start prediction of a finished one. */
  predictionSource: 'live' | 'stored' | null
  predictionGeneratedAt: string | null
  modelVersion: string | null
  mlPick: BestPick | null
}

export type MatchOddsMarket = 'moneyline' | 'total_games'

export interface MatchOddsRow {
  book: string
  p1Odds: number | null
  p2Odds: number | null
  line: number | null
  fetchedAt: string
}

export interface MatchOddsHistory {
  matchId: number
  market: MatchOddsMarket
  rows: MatchOddsRow[]
}

export interface PropsResponse {
  source: string | null
  count: number
  props: PropLine[]
}

export interface PropsAuditSummary {
  totalProps: number
  unresolvedPlayerCount: number
  unlinkedMatchCount: number
  missingStatsCount: number
  staleStatsCount: number
  unsupportedStatCount: number
  missingPredictionCount: number
  smallSampleCount: number
  topFlaggedExamples: string[]
}

export interface PropsAuditResponse extends PropsResponse {
  summary: PropsAuditSummary
}

export interface BestPick {
  pickType: string        // "moneyline" | "prop" | "derived"
  label: string           // e.g. "Moneyline", "Aces", "Set Score 2-0"
  pick: string            // e.g. "Sinner ML (-150)", "OVER 5.5"
  playerName: string | null
  // NOT comparable across pick types: a prob-vs-market edge for moneyline, a
  // projection-vs-line delta for props, a delta vs a fixed baseline for derived.
  edgePct: number
  confidence: string      // LOCK / STRONG / LEAN / PASS
  reasoning: string
  oddsAmerican?: number | null
  evPct?: number | null   // expected return %; null when the pick is unpriced
  modelProb?: number | null
  marketProb?: number | null
  kellyFraction?: number | null
  dataQualityFlags?: string[]
  oddsSource?: 'posted' | 'imputed' | 'unpriced' | string
}

export interface MatchBestPicks {
  matchId: number
  startUtc: string | null
  p1Name: string
  p2Name: string
  tour: string
  tourLabel?: string
  surface: string | null
  tournament: string | null
  round: string | null
  p1WinProb: number | null
  p2WinProb: number | null
  p1OddsAmerican: number | null
  p2OddsAmerican: number | null
  h2hP1Wins: number
  h2hP2Wins: number
  picks: BestPick[]
}

export interface BestPicksResponse {
  date: string
  count: number
  matches: MatchBestPicks[]
}

// ── Bankroll Builder ────────────────────────────────────────────────────────

export interface BankrollPick {
  matchId: number
  p1Name: string
  p2Name: string
  tour: string
  surface: string | null
  tournament: string | null
  round: string | null
  startUtc: string | null
  betType: string          // "ml" | "2-0" | "3-0" | "underdog_set" | "total_games"
  pickLabel: string
  pickSide: string
  ourProb: number
  marketProb: number | null
  oddsAmerican: number | null
  edgePct: number
  ev: number
  kellyFraction: number
  confidence: string
  reasoning: string
}

export interface ParlayLeg {
  matchId: number
  p1Name: string
  p2Name: string
  tour: string
  betType: string
  pickLabel: string
  ourProb: number
  oddsAmerican: number | null
  confidence: string
}

export interface SuggestedParlay {
  legs: ParlayLeg[]
  combinedProb: number
  combinedOddsAmerican: number
  combinedEv: number
  combinedKelly: number
  combinedEdgePct: number
  confidence: string
}

export interface BankrollBuilderResponse {
  date: string
  totalMatchesScanned: number
  singlesCount: number
  parlaysCount: number
  singles: BankrollPick[]
  parlays: SuggestedParlay[]
}

// ── Model track record (32b) ─────────────────────────────────────────────────

export type TrackSignal = 'positive' | 'neutral' | 'negative'
export type TrackGroup = 'ATP' | 'WTA' | 'ATP+WTA' | 'CHALLENGER'
export type TrackComponentName = 'market' | 'ensemble' | 'elo' | 'ml'

export interface LossComparison {
  mean: number
  standardError: number | null
  signal: TrackSignal
}

export interface TrackComponentRow {
  name: TrackComponentName
  logLoss: number
  brier: number
  vsMarket: LossComparison | null
}

export interface TrackGroupScores {
  group: TrackGroup
  n: number
  components: TrackComponentRow[]
}

export interface TrackCalibrationBin {
  low: number
  high: number
  n: number
  meanPredicted: number
  actualRate: number
}

export interface TrackCalibrationSeries {
  source: 'ensemble' | 'market' | 'ml'
  bins: TrackCalibrationBin[]
}

export interface TrackClvLine {
  group: 'all' | TrackGroup
  minGap: number
  eligible: number
  moved: number
  toward: number
  away: number
  meanMoveToward: number
}

export interface ModelPredictionsResponse {
  gradedAt: string
  modelVersion: string
  counts: {
    settled: number
    otherVersions: number
    incomplete: number
    graded: number
    withMarket: number
    withClose: number
  }
  groups: TrackGroupScores[]
  ensembleMarketGroups: TrackGroupScores[]
  calibration: TrackCalibrationSeries[]
  clv: TrackClvLine[]
  versions: ModelVersionCount[]
}

export interface ModelVersionCount {
  modelVersion: string
  settled: number
  served: boolean
}

export type TrackOddsType = 'standard' | 'goblin' | 'demon'

export interface TrackLineRow {
  stat: string
  oddsType: TrackOddsType
  settled: number
  overShare: number
  underShare: number
  pushShare: number
  overRate: number | null
  standardError: number | null
  breakEven: number | null
  signal: TrackSignal
}

export interface ModelPrizePicksLinesResponse {
  gradedAt: string
  excluded: { live: number, promo: number, incompleteScore: number, unjoined: number, notSettleable: number }
  rows: TrackLineRow[]
}

export type TrackTierName = 'LOCK' | 'STRONG' | 'LEAN'

export interface TrackTierRow {
  tier: TrackTierName
  decided: number
  hits: number
  pushes: number
  hitRate: number | null
  standardError: number | null
  verdict: 'accruing' | 'pass' | 'reject'
  verdictSampleSize: number
  verdictHitRate: number | null
  signal: TrackSignal
}

export interface ModelPropTiersResponse {
  gradedAt: string
  projectionVersion: string
  verdictSample: number
  breakEven: number
  excluded: { nonStandard: number, awaiting: number }
  tiers: TrackTierRow[]
  passSnapshotted: number
}

// ── Player page (32c) ────────────────────────────────────────────────────────

export interface PlayerEloPoint {
  asOf: string
  overall: number | null
  hard: number | null
  clay: number | null
  grass: number | null
}

export interface PlayerDetail {
  playerId: number
  name: string
  tour: string
  hand: 'R' | 'L' | null
  country: string | null
  birthDate: string | null
  rank: number | null
  elo: {
    overall: number | null
    hard: number | null
    clay: number | null
    grass: number | null
    asOf: string | null
    change: number | null
    tourRank: number | null
    tourRankOf: number | null
    history: PlayerEloPoint[]
  }
  nextMatch: {
    matchId: number
    startUtc: string | null
    matchDate: string
    tournament: string | null
    round: string | null
    surface: string | null
    opponentId: number
    opponentName: string
  } | null
  aliases: string[]
  statsComputedAt: string | null
}

/** Stored names: breakPct is BP converted, and the two per-game rates are per serve point. */
export interface ServeReturnMetrics {
  holdPct: number | null
  breakPct: number | null
  firstInPct: number | null
  firstWonPct: number | null
  secondWonPct: number | null
  retPtsWon: number | null
  acesPerGame: number | null
  dfPerGame: number | null
}

export type ServeReturnMetric = keyof ServeReturnMetrics
export type PlayerSurface = 'all' | 'Hard' | 'Clay' | 'Grass'

export interface PlayerSurfaceComparison {
  surface: PlayerSurface
  player: (ServeReturnMetrics & { matches: number }) | null
  tourAverage: ServeReturnMetrics & { players: number }
}

export interface PlayerServeReturn {
  tour: string
  surfaces: PlayerSurfaceComparison[]
}

export interface PlayerMatchLogRow {
  matchId: number
  matchDate: string
  tournament: string | null
  round: string | null
  surface: string | null
  bestOf: number
  opponentId: number
  opponentName: string
  opponentRank: number | null
  result: 'W' | 'L'
  score: string | null
  aces: number | null
  doubleFaults: number | null
  bpSaved: number | null
  bpFaced: number | null
  bpWon: number | null
  bpCreated: number | null
}

export interface WinLoss {
  wins: number
  losses: number
}

export interface PlayerRecord {
  windowStart: string
  all: WinLoss
  hard: WinLoss
  clay: WinLoss
  grass: WinLoss
  vsTop20: WinLoss
  decidingSets: WinLoss
  tieBreaks: WinLoss
}

export interface PlayerMatches {
  log: PlayerMatchLogRow[]
  record: PlayerRecord
}

export type PastPropOutcome = 'hit' | 'miss' | 'push' | 'pass' | 'void' | 'awaiting' | 'ungradable'

export interface PastProp {
  snapshotDate: string
  stat: string
  oddsType: string
  line: number
  actual: number | null
  recommendation: 'OVER' | 'UNDER' | null
  confidence: string | null
  outcome: PastPropOutcome
}

export interface PlayerProps {
  projectionVersion: string
  rows: PastProp[]
  summary: { hits: number, misses: number }
}
