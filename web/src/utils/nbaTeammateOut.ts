import type { NbaInjuryReport } from '~/types/nba'
import { gameSideTeam } from '~/utils/propFilters'

/** A player ESPN lists as not playing in one game; `id` is the ESPN athlete id the URL carries. */
export interface NbaTeammateOutOption {
  id: string
  playerId: number | null
  playerName: string
  team: string
  gameId: number
  status: string
  stale: boolean
}

interface OutGame {
  gameId: number
  awayTeam: string
  homeTeam: string
  injuryReport: NbaInjuryReport
}

interface OutRow {
  game: { gameId: number, awayTeam: string, homeTeam: string }
  row: { playerId: number, team: string | null }
}

// ESPN's only other stored status is Day-To-Day, which is not a confirmed absence.
const NOT_PLAYING = new Set(['out', 'suspension'])

export function teammateOutOptions(games: readonly OutGame[]): NbaTeammateOutOption[] {
  const options = new Map<string, NbaTeammateOutOption>()
  for (const game of games) {
    const report = game.injuryReport
    if (report.freshness === 'unavailable') continue
    for (const entry of report.injuries) {
      if (!NOT_PLAYING.has(entry.status.trim().toLowerCase())) continue
      if (entry.team !== game.awayTeam && entry.team !== game.homeTeam) continue
      // Filed under one team while ESPN lists the athlete on another: no side to trust.
      if (entry.athleteTeam !== null && entry.athleteTeam !== entry.team) continue
      const key = `${entry.espnAthleteId}:${game.gameId}`
      if (options.has(key)) continue
      options.set(key, {
        id: entry.espnAthleteId, playerId: entry.playerId, playerName: entry.playerName,
        team: entry.team, gameId: game.gameId, status: entry.status, stale: report.freshness === 'stale',
      })
    }
  }
  return [...options.values()].sort((left, right) => left.team.localeCompare(right.team) || left.playerName.localeCompare(right.playerName))
}

export function parseOutFilter(params: URLSearchParams): string | null {
  const value = params.get('out')
  return value !== null && /^\d{1,16}$/.test(value) ? value : null
}

/** An id from an old link that is not out on this board reads as no filter. */
export function activeOutFilter(value: string | null, options: readonly NbaTeammateOutOption[]): NbaTeammateOutOption | null {
  return value === null ? null : options.find(option => option.id === value) ?? null
}

/** Keeps the out player's teammates in that game. Every market stays, emptied ones included, so the pills do not reshuffle. */
export function filterTeammateOut<R extends OutRow, M extends { rows: R[] }>(markets: M[], option: NbaTeammateOutOption | null): M[] {
  if (option === null) return markets
  const keep = ({ game, row }: R) => game.gameId === option.gameId
    && gameSideTeam(row.team, game) === option.team
    && row.playerId !== option.playerId
  return markets.map(market => ({ ...market, rows: market.rows.filter(keep) }))
}
