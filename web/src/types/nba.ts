/** Mirrors `app/schemas/nba.py` (item 20e1). Dates are `YYYY-MM-DD`, times ISO UTC. */

export interface NbaRecord {
  wins: number
  losses: number
}

export interface NbaMoneyline {
  book: string
  homeOdds: number
  awayOdds: number
  /** Stored de-vigged probability of the home side. */
  homeWinProbability: number
  fetchedAt: string
}

export interface NbaSpread {
  book: string
  /** Book sign: negative means the home team is favored. */
  homeLine: number
  homeOdds: number
  awayOdds: number
  fetchedAt: string
}

export interface NbaTotal {
  book: string
  line: number
  overOdds: number
  underOdds: number
  fetchedAt: string
}

export interface NbaLineMove {
  market: 'spread' | 'total'
  book: string
  openLine: number
  currentLine: number
  openFetchedAt: string
  currentFetchedAt: string
}

export interface NbaSlateGame {
  gameId: number
  season: number
  week: number | null
  gameType: 'REG' | 'PIN' | 'PST'
  gameDate: string
  startUtc: string | null
  status: string
  awayTeam: string
  homeTeam: string
  awayTeamName: string
  homeTeamName: string
  /** Null until completed. */
  awayScore: number | null
  homeScore: number | null
  awayRecord: NbaRecord
  homeRecord: NbaRecord
  propLineCount: number
  moneyline: NbaMoneyline | null
  spread: NbaSpread | null
  total: NbaTotal | null
  lineMovement: NbaLineMove[]
}

export interface NbaSlateResponse {
  date: string
  previousDate: string | null
  nextDate: string | null
  games: NbaSlateGame[]
}

/** One digest line (38c2): gray reference, never a pick. */
export interface NbaSlateGap {
  gameId: number
  awayTeam: string
  homeTeam: string
  startUtc: string
  playerId: number
  playerName: string
  market: string
  line: number
  projection: number
  /** Projection minus line. */
  gap: number
  /** |gap| / line, the digest's rank. */
  gapShare: number
}

export interface NbaSlateGapsResponse {
  date: string
  modelVersion: string
  items: NbaSlateGap[]
}

export interface NbaLineStep {
  fetchedAt: string
  line: number
}

/** Pre-tip lines from one book per market, reduced to changes. */
export interface NbaLineHistory {
  market: 'spread' | 'total'
  book: string
  steps: NbaLineStep[]
}

/** `GET /nba/games/{id}`: the slate's game plus its line history. */
export interface NbaGameDetail extends NbaSlateGame {
  lineHistory: NbaLineHistory[]
  injuryReport: NbaInjuryReport
  teamStats: NbaTeamStatsContext | null
}

export type NbaTeamStat = 'points' | 'rebounds' | 'assists' | 'threes_made' | 'blocks'

export interface NbaTeamStatRate {
  perGame: number | null
  rank: number | null
  games: number
  rankedTeams: number
}

export interface NbaTeamSeasonStats {
  team: string
  completedGames: number
  stats: Record<NbaTeamStat, { for: NbaTeamStatRate, allowed: NbaTeamStatRate }>
}

export interface NbaTeamStatsContext {
  season: number
  beforeDate: string
  basis: 'stored_player_box_scores'
  away: NbaTeamSeasonStats
  home: NbaTeamSeasonStats
}

export interface NbaInjury {
  espnAthleteId: string
  playerId: number | null
  playerName: string
  team: string
  athleteTeam: string | null
  status: string
  detail: string | null
  sourceUpdatedAt: string | null
  returnDate: string | null
  fetchedAt: string
}

export interface NbaInjuryReport {
  source: 'ESPN'
  fetchedAt: string | null
  freshness: 'fresh' | 'stale' | 'unavailable'
  injuries: NbaInjury[]
}

export interface NbaLineOnlyRecent {
  gameDate: string
  opponent: string | null
  /** Null when a stat the market needs was not loaded for that game, never zero. */
  value: number | null
}

export interface NbaLineOnlyLine {
  playerId: number
  playerName: string
  position: string | null
  team: string | null
  market: string
  oddsType: string | null
  line: number
  fetchedAt: string
  /** The player's last 5 played games before this one, newest first. */
  recent: NbaLineOnlyRecent[]
  injury: NbaInjury | null
}

/** `GET /nba/games/{id}/line-only-props`: never a projection, edge or rank. */
export interface NbaLineOnlyProps {
  gameId: number
  lines: NbaLineOnlyLine[]
  injuryReport: NbaInjuryReport
  teamStats: NbaTeamStatsContext | null
}

export type NbaPropFlag = 'few_prior_games' | 'low_minutes' | 'no_over_probability' | 'integer_line'

/** A modelled line with the reference projection (20g2). Null means not served, never zero; gray, never a pick. */
export interface NbaPropLine extends NbaLineOnlyLine {
  projection: number | null
  gamesInSample: number
  priorMinutes: number | null
  /** Projection minus line, 2 places. */
  gap: number | null
  pOver: number | null
  pUnder: number | null
  overProbabilityVersion: string | null
  flags: NbaPropFlag[]
}

/** `GET /nba/games/{id}/props`. */
export interface NbaProps {
  gameId: number
  modelVersion: string
  lines: NbaPropLine[]
  injuryReport: NbaInjuryReport
  teamStats: NbaTeamStatsContext | null
}

export interface NbaPropBoardGame {
  gameId: number
  awayTeam: string
  homeTeam: string
  startUtc: string | null
  status: string
  lines: NbaPropLine[]
  lineOnlyLines: NbaLineOnlyLine[]
  injuryReport: NbaInjuryReport
  teamStats: NbaTeamStatsContext | null
}

/** `GET /nba/props`: one Eastern game date, with the game endpoints' line payloads. */
export interface NbaPropBoardResponse {
  date: string
  previousDate: string | null
  nextDate: string | null
  modelVersion: string
  games: NbaPropBoardGame[]
}

export interface NbaPlayerGameRef {
  gameId: number
  awayTeam: string
  homeTeam: string
  startUtc: string | null
  status: string
}

export interface NbaPlayerGame {
  gameDate: string
  opponent: string | null
  /** Null when a stat the market needs was not loaded for that game, never zero. */
  value: number | null
}

/** One stored line of a market. The model fields are null on a line-only market and where the projection is not served. */
export interface NbaPlayerRung {
  line: number
  oddsType: string | null
  fetchedAt: string
  gap: number | null
  pOver: number | null
  pUnder: number | null
  overProbabilityVersion: string | null
  flags: NbaPropFlag[]
}

export interface NbaPlayerMarket {
  market: string
  kind: 'modelled' | 'line-only'
  projection: number | null
  gamesInSample: number | null
  priorMinutes: number | null
  /** Line ascending, then odds type. */
  lines: NbaPlayerRung[]
  /** Newest first, up to 10. */
  recent: NbaPlayerGame[]
  /** Newest first, up to 20; empty when the player has no opponent that date. */
  opponentGames: NbaPlayerGame[]
}

/** `GET /nba/players/{id}/props`: display only, never a pick, rank or signal color. */
export interface NbaPlayerProps {
  playerId: number
  name: string
  position: string | null
  team: string | null
  date: string
  game: NbaPlayerGameRef | null
  opponent: string | null
  modelVersion: string
  injury: NbaInjury | null
  injuryReport: NbaInjuryReport
  teamStats: NbaTeamStatsContext | null
  markets: NbaPlayerMarket[]
  teammateSplit: NbaTeammateSplit | null
}

export type NbaSplitSide = 'with' | 'without' | 'before'

export interface NbaSplitGame {
  gameId: number
  gameDate: string
  opponent: string | null
  /** Keyed by the response's market names; null when a stat the market needs was not loaded. */
  values: Record<string, number | null>
}

export interface NbaSplitTeammate {
  playerId: number
  espnAthleteId: string
  playerName: string
  status: string
  stale: boolean
  /** Null when he has no box-score row for the team, so no game can be judged. */
  firstTeamGameDate: string | null
  /** One per game in `NbaTeammateSplit.games`. */
  sides: NbaSplitSide[]
}

/** This season's played games split by teammates listed out tonight: reference only (69). */
export interface NbaTeammateSplit {
  season: number
  team: string
  games: NbaSplitGame[]
  teammates: NbaSplitTeammate[]
}
