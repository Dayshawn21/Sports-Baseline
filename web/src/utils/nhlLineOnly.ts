import type { NhlLineOnlyLine, NhlLineOnlyMarket, NhlProjection } from '~/types/nhl'

export const NHL_LINE_ONLY_MARKETS = [
  'shots_on_goal', 'points', 'assists', 'goals', 'power_play_points', 'blocked_shots',
  'plus_minus', 'goalie_saves', 'hits', 'time_on_ice', 'goals_allowed', 'faceoffs_won',
] as const satisfies readonly NhlLineOnlyMarket[]

const MARKET_LABELS: Record<NhlLineOnlyMarket, string> = {
  shots_on_goal: 'Shots on Goal', points: 'Points', assists: 'Assists', goals: 'Goals',
  power_play_points: 'Power Play Points', blocked_shots: 'Blocked Shots', plus_minus: 'Plus/Minus',
  goalie_saves: 'Goalie Saves', hits: 'Hits', time_on_ice: 'Time On Ice', goals_allowed: 'Goals Allowed', faceoffs_won: 'Faceoffs Won',
}

const ODDS_TYPE_LABELS: Record<NhlLineOnlyLine['oddsType'], string> = { standard: 'Standard', demon: 'Demon', goblin: 'Goblin' }

export function nhlMarketLabel(market: NhlLineOnlyMarket): string {
  return MARKET_LABELS[market]
}

export function nhlPropLineLabel(market: NhlLineOnlyMarket, line: number): string {
  if (market === 'time_on_ice') return `${line} min`
  return `${market === 'plus_minus' && line > 0 ? '+' : ''}${line}`
}

function compareText(left: string, right: string): number {
  return left < right ? -1 : left > right ? 1 : 0
}

export interface NhlOddsTypeCount {
  oddsType: NhlLineOnlyLine['oddsType']
  label: string
  count: number
}

/** Standard, Goblin, Demon for the props header; zero counts are kept so the mix reads the same every game. */
export function nhlOddsTypeCounts(lines: readonly NhlLineOnlyLine[]): NhlOddsTypeCount[] {
  return (['standard', 'goblin', 'demon'] as const).map(oddsType => ({
    oddsType, label: ODDS_TYPE_LABELS[oddsType], count: lines.filter(line => line.oddsType === oddsType).length,
  }))
}

const ODDS_TYPE_ORDER: Record<NhlLineOnlyLine['oddsType'], number> = { standard: 0, goblin: 1, demon: 2 }

export interface NhlPropRung {
  line: number
  label: string
  oddsType: NhlLineOnlyLine['oddsType']
  oddsTypeLabel: string
  /** Projection minus this line; null when no projection is shown. */
  gap: number | null
}

export interface NhlPropListRow {
  key: string
  playerId: number
  playerName: string
  team: string | null
  position: string | null
  market: NhlLineOnlyMarket
  /** By line, then standard, goblin, demon; an offering repeated under another provider id shows once. */
  rungs: NhlPropRung[]
  /** The standard rung's label, or null when the player has none; alternates are never promoted to it. */
  standard: string | null
  /** The gap to the standard line, or null when there is no standard line or no projection. */
  standardGap: number | null
  /** One per player and market: the value does not depend on the line. */
  projection: NhlProjection
  /** The newest fetch across the player's offerings. */
  fetchedAt: string
}

export interface NhlPropListGroup {
  market: NhlLineOnlyMarket
  label: string
  rows: NhlPropListRow[]
}

function rungsFor(lines: readonly NhlLineOnlyLine[]): NhlPropRung[] {
  const seen = new Set<string>()
  return lines
    .filter(entry => !seen.has(`${entry.oddsType}:${entry.line}`) && seen.add(`${entry.oddsType}:${entry.line}`))
    .sort((a, b) => a.line - b.line || ODDS_TYPE_ORDER[a.oddsType] - ODDS_TYPE_ORDER[b.oddsType])
    .map(entry => ({
      line: entry.line, label: nhlPropLineLabel(entry.market, entry.line),
      oddsType: entry.oddsType, oddsTypeLabel: ODDS_TYPE_LABELS[entry.oddsType], gap: entry.projection.gap,
    }))
}

function newestFetch(lines: readonly NhlLineOnlyLine[]): string {
  return lines.reduce((newest, entry) => Date.parse(entry.fetchedAt) > Date.parse(newest) ? entry.fetchedAt : newest, lines[0].fetchedAt)
}

/** One row per player per market for the game page list, keyed by player id so two players with one name stay apart. */
export function nhlPropListGroups(lines: readonly NhlLineOnlyLine[]): NhlPropListGroup[] {
  const byMarket = new Map<NhlLineOnlyMarket, Map<number, NhlLineOnlyLine[]>>()
  for (const entry of lines) {
    const players = byMarket.get(entry.market) ?? new Map<number, NhlLineOnlyLine[]>()
    players.set(entry.playerId, [...(players.get(entry.playerId) ?? []), entry])
    byMarket.set(entry.market, players)
  }
  return NHL_LINE_ONLY_MARKETS.flatMap(market => {
    const players = byMarket.get(market)
    if (!players) return []
    const rows = [...players.values()].map((offerings): NhlPropListRow => {
      const rungs = rungsFor(offerings)
      const [first] = offerings
      return {
        key: `${market}:${first.playerId}`, playerId: first.playerId, playerName: first.playerName,
        team: first.team, position: first.position, market, rungs,
        standard: rungs.find(rung => rung.oddsType === 'standard')?.label ?? null,
        standardGap: rungs.find(rung => rung.oddsType === 'standard')?.gap ?? null,
        projection: first.projection,
        fetchedAt: newestFetch(offerings),
      }
    }).sort((a, b) => compareText(a.playerName, b.playerName) || a.playerId - b.playerId)
    return [{ market, label: nhlMarketLabel(market), rows }]
  })
}
