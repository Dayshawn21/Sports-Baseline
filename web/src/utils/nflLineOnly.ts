import type { NflLineOnlyLine, NflLineOnlyRecent } from '~/types/nfl'
import type { NflRecentBars } from '~/utils/nflPropCards'
import { filterNflSlateLinesByPosition, type NflPositionFilter } from '~/utils/nflPositions'

/** The order item 34 stored them in; any unknown market sorts after these. */
export const LINE_ONLY_MARKETS = [
  'receiving_targets', 'passing_touchdowns', 'interceptions', 'rushing_receiving_yards', 'passing_rushing_yards',
  'passing_rushing_receiving_touchdowns', 'field_goals_made', 'kicking_points', 'punts',
]

/** The fields of a recent game the card helpers read, so NBA's recent games fit too. */
export type LineOnlyRecentValue = Pick<NflLineOnlyRecent, 'value' | 'opponent'>

export interface NflLineOnlyRung {
  line: number
  oddsType: string | null
}

export interface NflLineOnlyRow {
  playerId: number
  playerName: string
  position: string | null
  rungs: NflLineOnlyRung[]
  recent: NflLineOnlyRecent[]
  /** Recent games over the standard line, among games with a value; null without a standard line. */
  overCount: number | null
  count: number | null
}

export interface NflLineOnlyGroup {
  market: string
  rows: NflLineOnlyRow[]
}

function marketRank(market: string): number {
  const index = LINE_ONLY_MARKETS.indexOf(market)
  return index === -1 ? LINE_ONLY_MARKETS.length : index
}

/** Recent games over the standard line, among games with a value; nulls without a standard line. */
export function overAgainstStandard(rungs: NflLineOnlyRung[], recent: LineOnlyRecentValue[]): Pick<NflLineOnlyRow, 'overCount' | 'count'> {
  const standard = rungs.find(rung => rung.oddsType === 'standard')
  if (!standard) return { overCount: null, count: null }
  const values = recent.flatMap(game => game.value === null ? [] : [game.value])
  return { overCount: values.filter(value => value > standard.line).length, count: values.length }
}

/** The rung a card leads with: the standard line, else the lowest rung. */
export function mainRung<R extends NflLineOnlyRung>(row: { rungs: R[] }): R {
  return row.rungs.find(rung => rung.oddsType === 'standard') ?? row.rungs[0]
}

/** Recent games as card bars, oldest to newest, on one scale with the standard line when there is one. */
export function lineOnlyBars(row: { rungs: NflLineOnlyRung[], recent: LineOnlyRecentValue[] }): NflRecentBars {
  const games = row.recent.flatMap(game => game.value === null ? [] : [{ value: game.value, opponentTeam: game.opponent }]).reverse()
  if (!games.length) return { bars: [], linePct: null }
  const line = row.rungs.find(rung => rung.oddsType === 'standard')?.line ?? null
  const scale = Math.max(line ?? 0, ...games.map(game => game.value))
  const pct = (value: number) => (scale > 0 ? Math.min(100, Math.max(0, (value / scale) * 100)) : 0)
  return {
    bars: games.map(game => ({
      ...game,
      heightPct: pct(game.value),
      vsLine: line === null ? null : game.value > line ? 'above' : game.value < line ? 'below' : 'push',
    })),
    linePct: line === null ? null : pct(line),
  }
}

/** One row per player per market, every rung of that player's line, grouped and ordered for display. */
export function lineOnlyGroups(lines: NflLineOnlyLine[], position: NflPositionFilter): NflLineOnlyGroup[] {
  const groups = new Map<string, Map<number, NflLineOnlyLine[]>>()
  for (const line of filterNflSlateLinesByPosition(lines, position)) {
    const players = groups.get(line.market) ?? new Map<number, NflLineOnlyLine[]>()
    players.set(line.playerId, [...(players.get(line.playerId) ?? []), line])
    groups.set(line.market, players)
  }
  return [...groups.entries()]
    .sort(([left], [right]) => marketRank(left) - marketRank(right))
    .map(([market, players]) => ({
      market,
      rows: [...players.values()].map(playerLines => {
        const [first] = playerLines
        const rungs = playerLines.map(line => ({ line: line.line, oddsType: line.oddsType })).sort((a, b) => a.line - b.line)
        return {
          playerId: first.playerId, playerName: first.playerName, position: first.position, rungs,
          recent: first.recent, ...overAgainstStandard(rungs, first.recent),
        }
      }).sort((a, b) => a.playerName.localeCompare(b.playerName)),
    }))
}
