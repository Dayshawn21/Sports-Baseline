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
}

export interface NhlLineOnlyProps {
  gameId: number
  lines: NhlLineOnlyLine[]
}

export interface NhlPlayerLine {
  line: number
  oddsType: 'standard' | 'demon' | 'goblin'
  fetchedAt: string
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
