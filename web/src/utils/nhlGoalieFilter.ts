import type { NhlGameContext, NhlGoalieSide } from '~/types/nhlContext'
import { nhlContextFreshness } from '~/utils/nhlContext'
import { GOALIE_MARKETS } from '~/utils/nhlPlayer'
import { gameSideTeam } from '~/utils/propFilters'

/** `known` is a confirmed or an expected starter. */
export type NhlGoalieFilter = 'any' | 'confirmed' | 'known'

export const NHL_GOALIE_FILTERS: Array<{ value: NhlGoalieFilter, label: string }> = [
  { value: 'any', label: 'Any' },
  { value: 'confirmed', label: 'Confirmed' },
  { value: 'known', label: 'Confirmed or expected' },
]

export interface NhlGoalieSides {
  away: NhlGoalieSide
  home: NhlGoalieSide
}

interface SlateGame {
  gameId: number
  startUtc: string | null
  context: NhlGameContext
}

interface GoalieRow {
  game: { gameId: number, awayTeam: string, homeTeam: string }
  row: { playerId: number, team: string | null, market: string }
}

const ALLOWED: Record<Exclude<NhlGoalieFilter, 'any'>, ReadonlySet<NhlGoalieSide['status']>> = {
  confirmed: new Set(['confirmed']),
  known: new Set(['confirmed', 'expected']),
}

export function parseGoalieFilter(params: URLSearchParams): NhlGoalieFilter {
  return NHL_GOALIE_FILTERS.find(option => option.value === params.get('goalie'))?.value ?? 'any'
}

/** A game's two sides, only from a fresh report: a stale or missing one says nothing about tonight's starter. */
export function goalieSides(games: readonly SlateGame[], now: Date): Map<number, NhlGoalieSides> {
  const sides = new Map<number, NhlGoalieSides>()
  for (const game of games) {
    const goalies = game.context.goalies
    if (nhlContextFreshness(goalies, game.startUtc, now) === 'fresh') sides.set(game.gameId, { away: goalies.away, home: goalies.home })
  }
  return sides
}

/** Skaters by the goalie they face, goalies only when they are the listed starter. Every market stays, emptied ones included. */
export function filterStartingGoalie<R extends GoalieRow, M extends { rows: R[] }>(
  markets: M[], filter: NhlGoalieFilter, sides: ReadonlyMap<number, NhlGoalieSides>,
): M[] {
  if (filter === 'any') return markets
  const allowed = ALLOWED[filter]
  const keep = ({ game, row }: R) => {
    const gameSides = sides.get(game.gameId)
    const team = gameSideTeam(row.team, game)
    if (!gameSides || team === null) return false
    const own = team === game.awayTeam ? gameSides.away : gameSides.home
    if (GOALIE_MARKETS.has(row.market)) return allowed.has(own.status) && own.playerId === row.playerId
    const opponent = team === game.awayTeam ? gameSides.home : gameSides.away
    return allowed.has(opponent.status)
  }
  return markets.map(market => ({ ...market, rows: market.rows.filter(keep) }))
}
