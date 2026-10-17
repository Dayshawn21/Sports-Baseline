import type { PropRankingRecord, PropRankingSlice } from '~/types/propRanking'
import type { TrackSignal } from '~/types/tennis'

// The slate is the web app's only NFL contract. /nfl/games, /nfl/projections, and
// /nfl/prospects remain on the API for direct use, but nothing here calls them,
// so their types live with the endpoints rather than as dead code.

export interface NflSlateLine {
  lineId: number
  playerId: number
  playerName: string
  position: string | null
  opponentTeam: string | null
  opponentPositionAverage: number | null
  recentForm: NflHistorySample
  opponentHistory: NflHistorySample
  opponentAllowedHistory: NflHistorySample
  market: string
  segment: string
  oddsType: string | null
  /** Null when there is no baseline, or no line, rather than a misleading 0. */
  projection: number | null
  line: number | null
  edge: number | null
  gamesInSample: number
  /** The season this baseline was computed from, not the newest season loaded. */
  baselineSeason: number | null
  /**
   * How the season was chosen: current_season, previous_season, largest_sample, no_data,
   * blended_seasons (anytime TD), or current_previous_blend (passing markets, 27d).
   */
  baselineReason: string
  /** Signed DVP adjustment for the scheduled opponent, null when evidence was unsafe. */
  opponentAdjustmentPct: number | null
  /** Historical player-games behind the scheduled opponent's position allowance. */
  opponentSampleGames: number | null
  /** Signed receiving-usage adjustment, null when not applicable or evidence was unsafe. */
  usageAdjustmentPct: number | null
  /** Usage-bearing player-games; null when usage is not applicable or missing. */
  usageSampleGames: number | null
  provider: string
  fetchedAt: string
  projectionModelVersion: string
  qualityFlags: string[]
  /** Sportsbook anytime-TD consensus; all null when no book priced this line. */
  bookProbability: number | null
  bookCount: number | null
  bookIncludesMargin: boolean | null
  bookFetchedAt: string | null
  /** Consensus with the book's margin removed, normalized across the game; null means not normalized, never "no margin". */
  bookProbabilityDevigged: number | null
  /** Out, Doubtful, or Questionable; null means not on this week's report (or not published), never "healthy". */
  injuryStatus: string | null
  practiceStatus: string | null
  injury: string | null
  /** This week's pre-game depth chart; null when the player is not listed. */
  depthPosition: string | null
  depthRank: number | null
  /** The player's most recent earlier depth chart, on any team. */
  previousDepthPosition: string | null
  previousDepthRank: number | null
  /** RB and TE anytime-TD lines only: the pre-week season-weighted offensive snap share (0 to 1) the model used. */
  snapShare: number | null
  /** The player's snap games behind `snapShare`; 0 means no history (the model used the position share), null means not applicable. */
  snapShareGames: number | null
  /** Display only (27g): fitted chance of going over the line; null means not shown here, never 50%. */
  pOver: number | null
  pUnder: number | null
  overProbabilityVersion: string | null
}

export interface NflHistorySample {
  average: number | null
  values: NflHistoryResult[]
}

export interface NflHistoryResult {
  value: number
  opponentTeam: string | null
}

export interface NflUnmatchedLine {
  lineId: number
  playerName: string
  providerTeam: string | null
  providerPosition: string | null
  market: string
  segment: string
  oddsType: string | null
  line: number
  provider: string
  fetchedAt: string
}

export interface NflSlateGame {
  gameId: number
  gameDate: string
  startUtc: string | null
  awayTeam: string
  homeTeam: string
  status: string
  lines: NflSlateLine[]
  odds: NflGameOdds | null
  awayContext: NflTeamContext | null
  homeContext: NflTeamContext | null
  weather: NflWeather
  model: NflGameModel | null
}

/** Display-only team-strength line; it did not beat closing lines, so it is never an edge. */
export interface NflGameModel {
  modelVersion: string
  homeElo: number
  awayElo: number
  homeWinProbability: number
  /** Book sign like `NflGameOdds.homeSpread`: negative when home is favored. */
  homeSpread: number
  total: number
  marketHomeWinProbability: number | null
}

export interface NflGameOdds {
  book: string
  homeMoneyline: number | null
  awayMoneyline: number | null
  homeSpread: number | null
  total: number | null
}

export interface NflWeather {
  venueType: string
  forecastFor: string | null
  temperatureF: number | null
  windMph: number | null
  windGustMph: number | null
  precipitationProbability: number | null
  fetchedAt: string | null
}

export interface NflTeamContext {
  games: number
  wins: number
  losses: number
  pointsForPerGame: number
  pointsAllowedPerGame: number
}

export interface NflLineStep {
  fetchedAt: string
  line: number
}

/** Pre-kickoff steps from one book; a spread line is the home spread in book sign, like `NflGameOdds.homeSpread`. */
export interface NflLineHistory {
  market: 'spread' | 'total'
  book: string
  steps: NflLineStep[]
}

/** `GET /nfl/games/{id}`, the game page's anchor. */
export interface NflGameDetail {
  gameId: number
  season: number
  week: number
  gameDate: string
  startUtc: string | null
  awayTeam: string
  homeTeam: string
  status: string
  lineHistory: NflLineHistory[]
}

export interface NflLineOnlyRecent {
  season: number
  week: number
  opponent: string | null
  /** Null when a stat the market needs was not loaded for that game, never zero. */
  value: number | null
}

export interface NflLineOnlyLine {
  playerId: number
  playerName: string
  position: string | null
  team: string | null
  market: string
  oddsType: string | null
  line: number
  fetchedAt: string
  recent: NflLineOnlyRecent[]
}

/** `GET /nfl/games/{id}/line-only-props` (item 35): never a projection, edge or rank. */
export interface NflLineOnlyProps {
  gameId: number
  lines: NflLineOnlyLine[]
}

export interface NflSeasonWeek {
  season: number
  week: number
}

/** Per-game means; a mean is null when no game has the stat. */
export interface NflPlayerSummary {
  games: number
  focusPerGame: number | null
  volumePerGame: number | null
  /** 0 to 1. */
  snapShare: number | null
}

export interface NflPlayerSplit extends NflPlayerSummary {
  label: string
}

export interface NflPlayerGame {
  gameId: number
  season: number
  week: number
  opponent: string
  isHome: boolean
  teamScore: number | null
  opponentScore: number | null
  /** 0 to 1; null when no snap row was loaded, never 0. */
  snapPct: number | null
  passingCompletions: number
  passingAttempts: number
  passingYards: number
  rushingAttempts: number
  rushingYards: number
  targets: number | null
  receptions: number
  receivingYards: number
  touchdowns: number
  prizepicksFantasyPoints: number | null
  /** The last pre-kickoff standard full-game line in the focus market, as 27a grades it. */
  focusLine: number | null
  focusOutcome: 'over' | 'under' | 'push' | null
}

export interface NflPlayerUsage {
  season: number
  week: number
  previousSeason: boolean
  passingAttempts: number
  rushingAttempts: number
  targets: number | null
  receptions: number
  snapPct: number | null
}

/** Over hits out of decided standard full-game lines this season; anecdote, never colored. */
export interface NflPastLineCount {
  market: string
  overs: number
  decided: number
}

/** `GET /nfl/players/{id}`, the one NFL player page, as of the current week. */
export interface NflPlayerDetail {
  playerId: number
  name: string
  position: string | null
  /** As of the week; null when cut or retired. */
  team: string | null
  season: number
  week: number
  depthPosition: string | null
  depthRank: number | null
  injuryStatus: string | null
  practiceStatus: string | null
  injury: string | null
  aliases: string[]
  statsThrough: NflSeasonWeek | null
  focusMarket: string | null
  summary: NflPlayerSummary
  gameLog: NflPlayerGame[]
  /** API field names in snake case, e.g. `rushing_attempts` or `snap_pct`. */
  usageStats: string[]
  usage: NflPlayerUsage[]
  pastLines: NflPastLineCount[]
  /** Per-leg standard break-even (57.7% for a 2-3 pick Power entry); the past-lines tick. */
  breakEven: number
  splits: NflPlayerSplit[]
}

export interface NflCurrentWeek {
  season: number
  week: number
}

export interface NflSlateResponse {
  season: number
  week: number
  gameCount: number
  lineCount: number
  unmatchedCount: number
  games: NflSlateGame[]
  unmatched: NflUnmatchedLine[]
}

export interface NflNoteInjury {
  playerId: number
  playerName: string
  team: string
  position: string
  injuryStatus: string | null
  practiceStatus: string | null
  injury: string | null
}

export interface NflNoteDepthChange {
  playerId: number
  playerName: string
  team: string
  depthPosition: string
  depthRank: number
  previousDepthPosition: string | null
  previousDepthRank: number | null
  change: 'promoted' | 'demoted' | 'new'
}

export interface NflLineMove {
  market: 'spread' | 'total'
  book: string
  /** Spread is the home line in book sign: negative when home is favored. */
  openLine: number
  openFetchedAt: string
  currentLine: number
  currentFetchedAt: string
  /** Null when only one pre-kickoff line is stored. */
  move: number | null
}

export interface NflRecentResult {
  week: number
  opponent: string
  isHome: boolean
  pointsFor: number
  pointsAgainst: number
  result: 'W' | 'L' | 'T'
}

export interface NflTeamForm {
  team: string
  restDays: number | null
  shortWeek: boolean
  recent: NflRecentResult[]
}

export interface NflTeamStat {
  value: number | null
  /** League rank, 1 = best; null when the value is missing. */
  rank: number | null
}

/** Season to date before the slate week. Success rates are 0 to 1. */
export interface NflTeamStats {
  team: string
  games: number
  efficiencyGames: number
  points: NflTeamStat
  passYards: NflTeamStat
  rushYards: NflTeamStat
  plays: NflTeamStat
  epaPerPlay: NflTeamStat
  successRate: NflTeamStat
  pointsAllowed: NflTeamStat
  passYardsAllowed: NflTeamStat
  rushYardsAllowed: NflTeamStat
  playsAllowed: NflTeamStat
  epaPerPlayAllowed: NflTeamStat
  successRateAllowed: NflTeamStat
}

export type NflQbChangeReason = 'injured' | 'backup_started' | 'depth_chart'

/** A team's QB differs from the one its recent games, and so the game model, were built on. */
export interface NflQbChange {
  team: string
  /** Latest depth-chart QB1; most attempts only when no chart is stored. */
  usualStarter: string
  reasons: NflQbChangeReason[]
  /** Each pair is set only with its reason; weeks are the latest stored, not always the slate week. */
  injuryStatus: string | null
  injuryWeek: number | null
  lastGameQb: string | null
  lastGameWeek: number | null
  previousQb1: string | null
}

export interface NflFairPrice {
  source: 'pinnacle' | 'consensus'
  line: number | null
  /** De-vigged, home or over side. */
  firstProbability: number
  fetchedAt: string
}

export interface NflBestSide {
  side: 'home' | 'away' | 'over' | 'under'
  /** Book sign: negative home spread = home favored. */
  line: number | null
  odds: number
  book: string
  provider: string
  fetchedAt: string
  /** At most one is set: EV at the fair line, else points off it. */
  evPct: number | null
  pointsVsFair: number | null
}

export interface NflBestMarket {
  market: 'moneyline' | 'spread' | 'total'
  fair: NflFairPrice | null
  sides: NflBestSide[]
}

/** Each side's best price across books beside a fair price; a reference, never a pick. */
export interface NflBestLine {
  maxAgeHours: number
  markets: NflBestMarket[]
}

/** Display-only pre-bet context; never feeds an edge or rank. */
export interface NflGameNotes {
  gameId: number
  awayTeam: string
  homeTeam: string
  injuries: NflNoteInjury[]
  depthChanges: NflNoteDepthChange[]
  lineMovement: NflLineMove[]
  awayForm: NflTeamForm
  homeForm: NflTeamForm
  awayStats: NflTeamStats
  homeStats: NflTeamStats
  /** Null until the game is final. */
  awayScore: number | null
  homeScore: number | null
  awayQbChange: NflQbChange | null
  homeQbChange: NflQbChange | null
  /** Null once kicked off or with no fresh book. */
  bestLine: NflBestLine | null
}

export interface NflGameNotesResponse {
  season: number
  week: number
  games: NflGameNotes[]
}

/** Model track record (33d). Signals come from the API's 2 SE rules, never from a raw number here. */
export type NflRankingSlice = PropRankingSlice

export type NflModelRanking = PropRankingRecord

export interface NflHitRow {
  calls: number
  hits: number
  pushes: number
  hitRate: number | null
  standardError: number | null
  signal: TrackSignal
}

export interface NflOverProbabilityRead {
  oddsType: 'standard' | 'goblin' | 'demon' | 'all'
  scored: number
  unscored: number
  meanPredicted: number | null
  overRate: number | null
  brier: number | null
}

export interface NflModelPropLines {
  gradedAt: string
  season: number
  modelVersion: string
  breakEven: number
  coverage: { loaded: number, settled: number, voidDnp: number, unsettleableSegment: number, weekNotLoaded: number }
  calls: NflHitRow
  byEdge: (NflHitRow & { bucket: 'small' | 'medium' | 'large', label: string })[]
  byMarket: (NflHitRow & { market: string })[]
  byWeek: (NflHitRow & { week: number })[]
  overProbability: NflOverProbabilityRead[]
  reliability: { n: number, meanPredicted: number, observed: number }[]
}

export interface NflClvRow {
  n: number
  meanClv: number | null
  standardError: number | null
  toward: number
  away: number
  flat: number
  wins: number
  losses: number
  pushes: number
}

export interface NflClvMarket {
  market: 'spread' | 'total'
  modelVersion: string
  graded: number
  excluded: Record<string, number>
  medianLeadHours: number | null
  minLeadHours: number | null
  verdict: 'accruing' | 'pass' | 'reject'
  verdictWeeks: number[]
  headline: NflClvRow
  all: NflClvRow
  early: NflClvRow
  late: NflClvRow
  signal: TrackSignal
}

export interface NflModelClv {
  gradedAt: string
  season: number
  rule: { pickThreshold: number, verdictPicks: number }
  markets: NflClvMarket[]
}

export interface NflFitMarket {
  market: string
  cases: number
  pairs: number
  ece: number
  worstGap: number | null
  brier: number
  normalBrier: number
  verdict: 'show' | 'hide'
  atProjectionPredicted: number
  atProjectionObserved: number
}

export interface NflModelFit {
  fitSeason: number
  projectionVersion: string
  served: boolean
  rule: { minCases: number, maxEce: number, maxBinGap: number, minBinPairs: number }
  markets: NflFitMarket[]
}
