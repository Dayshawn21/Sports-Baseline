import type { MatchPrediction, PlayerMatchLogRow, RecentMatchResult } from '~/types/tennis'
import { marketKey, type TennisBoardCategory, type TennisBoardLine } from '~/utils/tennisPropBoard'

export type TennisFormWindow = '5' | '10' | 'opp'

export const FORM_PARAM = 'form'
export const LONG_WINDOW_MATCHES = 10
export const MARKET_PARAM = 'market'
export const MATCH_PARAM = 'match'
export const PROP_PARAM = 'prop'

export interface PlayerMarketTab {
  market: string
  label: string
  rated: TennisBoardLine[]
  review: TennisBoardLine[]
}

export interface PlayerMatchOption {
  matchId: number | null
  matchup: string | null
  startTime: string | null
  opponentId: number | null
  opponentName: string | null
}

export interface FormWindowOption {
  window: TennisFormWindow
  label: string
  disabledReason: string | null
}

function normalized(value: string | null | undefined): string {
  return (value ?? '').trim().toLowerCase()
}

export function isPlayerLine(line: Pick<TennisBoardLine, 'playerId' | 'playerName'>, playerId: number, playerName: string): boolean {
  if (line.playerId != null) return line.playerId === playerId
  return normalized(line.playerName) !== '' && normalized(line.playerName) === normalized(playerName)
}

/** The board's categories cut down to one player; a market the player has no line in gets no tab. */
export function playerMarketTabs(categories: TennisBoardCategory[], playerId: number, playerName: string): PlayerMarketTab[] {
  return categories
    .map(category => ({
      market: category.market,
      label: category.label,
      rated: category.rateable.filter(line => isPlayerLine(line, playerId, playerName)),
      review: category.other.filter(line => isPlayerLine(line, playerId, playerName)),
    }))
    .filter(tab => tab.rated.length + tab.review.length > 0)
}

function opponentOf(prediction: MatchPrediction | undefined, playerId: number, playerName: string): Pick<PlayerMatchOption, 'opponentId' | 'opponentName'> {
  if (!prediction) return { opponentId: null, opponentName: null }
  const isFirst = prediction.p1Id != null ? prediction.p1Id === playerId : normalized(prediction.p1Name) === normalized(playerName)
  return isFirst
    ? { opponentId: prediction.p2Id ?? null, opponentName: prediction.p2Name }
    : { opponentId: prediction.p1Id ?? null, opponentName: prediction.p1Name }
}

/** One option per match the tab's lines belong to, earliest start first. */
export function matchOptions(lines: TennisBoardLine[], predictions: MatchPrediction[], playerId: number, playerName: string): PlayerMatchOption[] {
  const byMatch = new Map<number | null, TennisBoardLine>()
  for (const line of lines) if (!byMatch.has(line.matchId)) byMatch.set(line.matchId, line)
  return [...byMatch.entries()]
    .map(([matchId, line]) => {
      const prediction = matchId == null ? undefined : predictions.find(item => item.matchId === matchId)
      return { matchId, matchup: line.matchup, startTime: line.startTime ?? prediction?.startUtc ?? null, ...opponentOf(prediction, playerId, playerName) }
    })
    .sort((left, right) => (left.startTime ?? '9999').localeCompare(right.startTime ?? '9999'))
}

export function logRowToRecent(row: PlayerMatchLogRow): RecentMatchResult {
  return {
    matchDate: row.matchDate,
    opponentName: row.opponentName,
    score: row.score,
    result: row.result,
    aces: row.aces,
    doubleFaults: row.doubleFaults,
    breakChancesCreated: row.bpCreated,
    breakPointsConverted: row.bpWon,
  }
}

/** Last 5 is the default and is never written to the URL. */
export function parseTennisFormWindow(params: URLSearchParams): TennisFormWindow {
  const value = params.get(FORM_PARAM)
  return value === '10' || value === 'opp' ? value : '5'
}

function newestFirst(log: PlayerMatchLogRow[]): PlayerMatchLogRow[] {
  return [...log].sort((left, right) => right.matchDate.localeCompare(left.matchDate))
}

function meetings(log: PlayerMatchLogRow[], opponentId: number | null): PlayerMatchLogRow[] {
  return opponentId == null ? [] : log.filter(row => row.opponentId === opponentId)
}

export function formWindowOptions(log: PlayerMatchLogRow[], opponentId: number | null, opponentName: string | null): FormWindowOption[] {
  const label = opponentName ? `vs ${opponentName}` : 'vs Opponent'
  const reason = opponentId == null ? 'No opponent for this match' : meetings(log, opponentId).length === 0 ? `No earlier matches against ${opponentName ?? 'this opponent'}` : null
  return [
    { window: '5', label: 'Last 5', disabledReason: null },
    { window: '10', label: 'Last 10', disabledReason: null },
    { window: 'opp', label, disabledReason: reason },
  ]
}

/** The asked-for window, or Last 5 when it cannot be shown. */
export function resolveFormWindow(options: FormWindowOption[], window: TennisFormWindow): TennisFormWindow {
  return options.find(option => option.window === window)?.disabledReason === null ? window : '5'
}

export function formWindowSample(log: PlayerMatchLogRow[], window: TennisFormWindow, opponentId: number | null): RecentMatchResult[] {
  const count = window === '5' ? 5 : LONG_WINDOW_MATCHES
  const rows = window === 'opp' ? newestFirst(meetings(log, opponentId)) : newestFirst(log).slice(0, count)
  return rows.map(logRowToRecent)
}

/** Only Last 10 can come up short of its name. */
export function formShortNote(window: TennisFormWindow, matches: number): string | null {
  return window === '10' && matches > 0 && matches < LONG_WINDOW_MATCHES ? `${matches} of ${LONG_WINDOW_MATCHES} matches` : null
}

type PlayerMatchSides = Pick<MatchPrediction, 'matchId' | 'p1Name' | 'p2Name' | 'p1Id' | 'p2Id'>
type LinkedLine = Pick<TennisBoardLine, 'id' | 'playerId' | 'playerName' | 'matchId' | 'statType'>

/** The line's own player id, else the id of the side of its match with the same name. */
export function propPlayerId(line: Pick<LinkedLine, 'playerId' | 'playerName' | 'matchId'>, matches: PlayerMatchSides[]): number | null {
  if (line.playerId != null) return line.playerId
  const name = normalized(line.playerName)
  const match = matches.find(item => item.matchId === line.matchId)
  if (!match || name === '') return null
  if (normalized(match.p1Name) === name) return match.p1Id ?? null
  return normalized(match.p2Name) === name ? match.p2Id ?? null : null
}

/** Where a prop row opens: the player's page on the line's market, match and line; null when the player cannot be resolved. */
export function propPlayerPath(line: LinkedLine, matches: PlayerMatchSides[]): string | null {
  const playerId = propPlayerId(line, matches)
  if (playerId == null) return null
  const query = new URLSearchParams({ [MARKET_PARAM]: marketKey(line.statType) })
  if (line.matchId != null && Number.isSafeInteger(line.matchId) && line.matchId > 0) query.set(MATCH_PARAM, String(line.matchId))
  if (Number.isSafeInteger(line.id) && line.id > 0) query.set(PROP_PARAM, String(line.id))
  return `/tennis/player/${playerId}?${query}`
}

const ORIGINS: Array<[RegExp, string]> = [
  [/^\/tennis\/board$/, 'Tennis props'],
  [/^\/tennis\/match\/\d+\?tab=props(&[a-z]+=[A-Za-z0-9_]+)*$/, 'Match props'],
]

export interface PlayerPageOrigin {
  path: string
  label: string
}

/** The page a row was opened from, taken from router state; anything but the board or a match's props tab is ignored. */
export function playerPageOrigin(state: unknown): PlayerPageOrigin | null {
  const from = typeof state === 'object' && state !== null && 'from' in state ? (state as { from: unknown }).from : null
  if (typeof from !== 'string') return null
  const origin = ORIGINS.find(([pattern]) => pattern.test(from))
  return origin ? { path: from, label: origin[1] } : null
}
