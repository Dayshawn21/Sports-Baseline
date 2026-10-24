import type { NhlGameContext } from '~/types/nhlContext'

/** CamelCase responses from `app/schemas/nhl.py`; dates are Eastern calendar dates. */
export type NhlBook = 'draftkings' | 'bet365'

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
