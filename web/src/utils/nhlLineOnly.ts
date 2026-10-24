import type { NhlLineOnlyLine, NhlLineOnlyMarket } from '~/types/nhl'

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

export interface NhlLineOnlyRow extends NhlLineOnlyLine {
  key: string
  lineLabel: string
  oddsTypeLabel: string
}

export interface NhlLineOnlyGroup {
  market: NhlLineOnlyMarket
  label: string
  rows: NhlLineOnlyRow[]
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

/** One row per offering; repeated players/prices never collapse alternate provider ids. */
export function nhlLineOnlyGroups(lines: readonly NhlLineOnlyLine[]): NhlLineOnlyGroup[] {
  const groups = new Map<NhlLineOnlyMarket, NhlLineOnlyRow[]>()
  for (const line of lines) {
    const rows = groups.get(line.market) ?? []
    rows.push({
      ...line, key: `${line.provider}:${line.providerPropId}`,
      lineLabel: nhlPropLineLabel(line.market, line.line), oddsTypeLabel: ODDS_TYPE_LABELS[line.oddsType],
    })
    groups.set(line.market, rows)
  }
  return NHL_LINE_ONLY_MARKETS.flatMap(market => {
    const rows = groups.get(market)
    return rows ? [{
      market, label: nhlMarketLabel(market),
      rows: rows.sort((a, b) => compareText(a.playerName, b.playerName) || a.playerId - b.playerId
        || compareText(a.oddsType, b.oddsType) || a.line - b.line || compareText(a.providerPropId, b.providerPropId)),
    }] : []
  })
}
