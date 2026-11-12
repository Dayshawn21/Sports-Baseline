import type { NhlContextFreshness, NhlGameContext, NhlGoalieContext, NhlInjury } from '~/types/nhlContext'

/** CamelCase responses from `app/schemas/nhl.py`; dates are Eastern calendar dates. */
export type NhlBook = 'draftkings' | 'fanduel' | 'bet365'

export interface NhlMoneyline {
  book: NhlBook
  homeOdds: number
  awayOdds: number
  homeWinProbability: number
  fetchedAt: string
}

export interface NhlSpread {
  book: NhlBook
  homeLine: number
  homeOdds: number
  awayOdds: number
  fetchedAt: string
}

export interface NhlTotal {
  book: NhlBook
  line: number
  overOdds: number
  underOdds: number
  fetchedAt: string
}

export interface NhlLineMove {
  market: 'spread' | 'total'
  book: NhlBook
  openLine: number
  currentLine: number
  openFetchedAt: string
  currentFetchedAt: string
}

/** W-L-OT as the NHL standings write it: overtime and shootout losses are the third number. */
export interface NhlRecord {
  wins: number
  losses: number
  otLosses: number
}

export interface NhlSlateGame {
  gameId: number
  season: number
  week: number | null
  gameType: 'REG' | 'PST'
  gameDate: string
  startUtc: string | null
  status: string
  awayTeam: string
  homeTeam: string
  awayTeamName: string
  homeTeamName: string
  awayScore: number | null
  homeScore: number | null
  endPeriod: 'REG' | 'OT' | 'SO' | null
  awayRecord: NhlRecord
  homeRecord: NhlRecord
  propLineCount: number
  moneyline: NhlMoneyline | null
  spread: NhlSpread | null
  total: NhlTotal | null
  lineMovement: NhlLineMove[]
  context: NhlGameContext
}

export interface NhlSlateResponse {
  date: string
  previousDate: string | null
  nextDate: string | null
  games: NhlSlateGame[]
}

export interface NhlLineHistory {
  market: 'spread' | 'total'
  book: NhlBook
  steps: { fetchedAt: string, line: number }[]
}

export interface NhlGameDetail extends NhlSlateGame {
  lineHistory: NhlLineHistory[]
}

export type NhlLineOnlyMarket =
  | 'shots_on_goal' | 'points' | 'assists' | 'goals' | 'power_play_points' | 'blocked_shots'
  | 'plus_minus' | 'goalie_saves' | 'hits' | 'time_on_ice' | 'goals_allowed' | 'faceoffs_won'

export type NhlProjectionFlag =
  | 'few_prior_games' | 'low_toi' | 'not_center' | 'no_goalie_report' | 'starter_unconfirmed'
  | 'other_starter_expected' | 'context_stale' | 'injured_out' | 'injury_listed' | 'injury_context_stale'
  | 'integer_line' | 'no_over_probability'

/** `value` and `gap` are null, never zero, when no number is shown; `flags` says why or what to qualify. */
export interface NhlProjection {
  modelVersion: string
  value: number | null
  gamesInSample: number
  gap: number | null
  /** P(over) at this line; null unless the market's fit is served, a number is shown and the line is not a whole number. P(under) is 1 minus it. */
  pOver: number | null
  flags: NhlProjectionFlag[]
}

export interface NhlLineOnlyLine {
  provider: 'prizepicks'
  providerPropId: string
  playerId: number
  playerName: string
  position: string | null
  team: string | null
  market: NhlLineOnlyMarket
  oddsType: 'standard' | 'demon' | 'goblin'
  line: number
  fetchedAt: string
  projection: NhlProjection
}

/** A line as served: its own gap, P(over) and line flags, with the player-market projection sent once beside it. */
export interface NhlLineOnlyWireLine extends Omit<NhlLineOnlyLine, 'projection'> {
  gap: number | null
  pOver: number | null
  flags: NhlProjectionFlag[]
}

/** One per player and market; carries no gap or P(over), which belong to each line. */
export interface NhlMarketProjection {
  playerId: number
  market: NhlLineOnlyMarket
  modelVersion: string
  value: number | null
  gamesInSample: number
  flags: NhlProjectionFlag[]
}

export interface NhlLineOnlyWireProps extends Omit<NhlLineOnlyProps, 'lines'> {
  lines: NhlLineOnlyWireLine[]
  projections: NhlMarketProjection[]
}

export interface NhlPropBoardWireGame extends Omit<NhlPropBoardGame, 'lines'> {
  lines: NhlLineOnlyWireLine[]
  projections: NhlMarketProjection[]
}

export interface NhlPropBoardWireResponse extends Omit<NhlPropBoardResponse, 'games'> {
  games: NhlPropBoardWireGame[]
}

export interface NhlLineOnlyProps {
  gameId: number
  /** The P(over) fit behind the numbers; null when none is served. */
  overProbabilityVersion: string | null
  lines: NhlLineOnlyLine[]
}

export interface NhlPropBoardGame {
  gameId: number
  awayTeam: string
  homeTeam: string
  startUtc: string | null
  status: string
  lines: NhlLineOnlyLine[]
}

export interface NhlPropBoardResponse {
  overProbabilityVersion: string | null
  date: string
  previousDate: string | null
  nextDate: string | null
  games: NhlPropBoardGame[]
}

export interface NhlPlayerLine {
  line: number
  oddsType: 'standard' | 'demon' | 'goblin'
  fetchedAt: string
  /** Projection minus this rung's line; null when the market shows no projection. */
  gap: number | null
  /** This rung's own P(over) and P(under); null unless the market's fit is served and the line is not a whole number. */
  pOver: number | null
  pUnder: number | null
  /** Only `integer_line` or `no_over_probability`: why this rung has no probability. */
  flags: NhlProjectionFlag[]
}

/** `value` is null when the box score left the stat unloaded, never zero; time on ice is minutes. Goalie markets count started games only. */
export interface NhlPlayerGame {
  gameDate: string
  opponent: string | null
  value: number | null
}

export interface NhlPlayerMarket {
  market: NhlLineOnlyMarket
  lines: NhlPlayerLine[]
  /** One per market; its own `gap` is null because each rung carries one. */
  projection: NhlProjection
  /** Newest first, up to 10; Last 5 is the first five. */
  recent: NhlPlayerGame[]
  /** Newest first, season 2023 onward; empty when the opponent is unknown. */
  opponentGames: NhlPlayerGame[]
}

export interface NhlPlayerGameRef {
  gameId: number
  gameType: 'REG' | 'PST'
  awayTeam: string
  homeTeam: string
  startUtc: string | null
  status: string
}

export interface NhlPlayerInjury {
  fetchedAt: string | null
  sourceTimestamp: string | null
  freshness: NhlContextFreshness
  entry: NhlInjury | null
}

export interface NhlPlayerProps {
  overProbabilityVersion: string | null
  playerId: number
  name: string
  position: string | null
  team: string | null
  date: string
  game: NhlPlayerGameRef | null
  opponent: string | null
  injury: NhlPlayerInjury
  goalies: NhlGoalieContext | null
  markets: NhlPlayerMarket[]
}

/** One settled frozen line on the player page's projection history (60b). */
export interface NhlProjectionHistoryPoint {
  gameId: number
  gameDate: string
  season: number
  opponentId: number
  /** The opposing team's code. */
  opponentName: string
  stat: NhlLineOnlyMarket
  line: number
  /** Frozen before puck drop; null for a gated line, never recomputed. */
  projection: number | null
  actual: number
  snapshotAt: string
}

export interface NhlProjectionHistory {
  projectionVersion: string
  points: NhlProjectionHistoryPoint[]
  /** Frozen lines on completed games whose box score has not loaded or lacks the stat yet. */
  unsettled: number
}
