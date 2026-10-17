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
}

/** `GET /nba/games/{id}/line-only-props`: never a projection, edge or rank. */
export interface NbaLineOnlyProps {
  gameId: number
  lines: NbaLineOnlyLine[]
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
}
