import type { NbaInjury, NbaLineOnlyLine, NbaLineOnlyRecent } from '~/types/nba'
import { overAgainstStandard, type NflLineOnlyRung } from '~/utils/nflLineOnly'

const DOUBLE_DOUBLE = 'double_double'

/** `NbaLineOnlyMarket` order (20c); any unknown market sorts after these. */
export const NBA_LINE_ONLY_MARKETS = [
  'points', 'rebounds', 'assists', 'threes_made', 'blocks',
  'points_rebounds_assists', 'points_rebounds', 'points_assists', 'rebounds_assists', DOUBLE_DOUBLE,
]

const MARKET_LABELS: Record<string, string> = {
  points: 'Points', rebounds: 'Rebounds', assists: 'Assists', threes_made: '3-pointers made', blocks: 'Blocks',
  points_rebounds_assists: 'Pts + reb + ast', points_rebounds: 'Pts + reb', points_assists: 'Pts + ast',
  rebounds_assists: 'Reb + ast', double_double: 'Double-double',
}

export function nbaMarketLabel(market: string): string {
  return MARKET_LABELS[market] ?? market
}

/** A recent result as the card prints it: double-double settles 1 or 0, so it reads yes or no. */
export function nbaRecentValueLabel(market: string, value: number | null): string {
  if (value === null) return '--'
  if (market === DOUBLE_DOUBLE) return value >= 1 ? 'yes' : 'no'
  return String(value)
}

export interface NbaLineOnlyRow {
  playerId: number
  playerName: string
  position: string | null
  team: string | null
  injury: NbaInjury | null
  rungs: NflLineOnlyRung[]
  recent: NbaLineOnlyRecent[]
  overCount: number | null
  count: number | null
}

export interface NbaLineOnlyGroup {
  market: string
  rows: NbaLineOnlyRow[]
}

function marketRank(market: string): number {
  const index = NBA_LINE_ONLY_MARKETS.indexOf(market)
  return index === -1 ? NBA_LINE_ONLY_MARKETS.length : index
}

/** One row per player per market with every rung, grouped by market in stored order, rows by name. */
export function nbaLineOnlyGroups(lines: NbaLineOnlyLine[]): NbaLineOnlyGroup[] {
  const groups = new Map<string, Map<number, NbaLineOnlyLine[]>>()
  for (const line of lines) {
    const players = groups.get(line.market) ?? new Map<number, NbaLineOnlyLine[]>()
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
          playerId: first.playerId, playerName: first.playerName, position: first.position, team: first.team, injury: first.injury ?? null,
          rungs, recent: first.recent, ...overAgainstStandard(rungs, first.recent),
        }
      }).sort((a, b) => a.playerName.localeCompare(b.playerName)),
    }))
}
