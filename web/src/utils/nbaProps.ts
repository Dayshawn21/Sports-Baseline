import type { NbaInjury, NbaLineOnlyRecent, NbaPropFlag, NbaPropLine } from '~/types/nba'
import { NBA_LINE_ONLY_MARKETS } from '~/utils/nbaLineOnly'
import { mainRung, overAgainstStandard } from '~/utils/nflLineOnly'

/** `NbaPropMarket` order (20g2): the modelled markets, every NBA market except double-double. */
export const NBA_PROP_MARKETS = NBA_LINE_ONLY_MARKETS.filter(market => market !== 'double_double')

export interface NbaPropRung {
  line: number
  oddsType: string | null
  pOver: number | null
  pUnder: number | null
  gap: number | null
  flags: NbaPropFlag[]
}

/** The main rung's projection, as the card prints it; gray, never a pick. */
export interface NbaProjectionRow {
  projection: string
  gap: string
  pOver: string | null
  pUnder: string | null
}

export interface NbaPropCard {
  playerId: number
  playerName: string
  position: string | null
  team: string | null
  injury: NbaInjury | null
  rungs: NbaPropRung[]
  main: NbaPropRung
  /** Every rung but the main one, with its own P(over) when served: `9.5 demon · 31%`. */
  also: string[]
  /** Null when the player is not eligible; `flagText` says why. */
  projectionRow: NbaProjectionRow | null
  gamesInSample: number
  priorMinutes: number | null
  flagText: string | null
  recent: NbaLineOnlyRecent[]
  overCount: number | null
  count: number | null
}

export interface NbaPropGroup {
  market: string
  cards: NbaPropCard[]
}

const FLAG_TEXT: Record<NbaPropFlag, string> = {
  few_prior_games: 'No projection: fewer than 10 earlier games',
  low_minutes: 'No projection: under 20 minutes a game',
  no_over_probability: 'P(over) not fitted for this market',
  integer_line: 'Whole-number line: no P(over)',
}

export function nbaPropFlagText(flag: NbaPropFlag): string {
  return FLAG_TEXT[flag]
}

function marketRank(market: string): number {
  const index = NBA_PROP_MARKETS.indexOf(market)
  return index === -1 ? NBA_PROP_MARKETS.length : index
}

function percent(probability: number): string {
  return `${Math.round(probability * 100)}%`
}

function oneDecimal(value: number): string {
  // Avoids "-0.0" when a small negative rounds to zero.
  const rounded = Math.round(value * 10) / 10
  return (rounded === 0 ? 0 : rounded).toFixed(1)
}

export function signedGap(gap: number): string {
  const text = oneDecimal(gap)
  return gap > 0 && text !== '0.0' ? `+${text}` : text
}

export function rungLabel(rung: Pick<NbaPropRung, 'line' | 'oddsType' | 'pOver'>): string {
  const name = rung.oddsType && rung.oddsType !== 'standard' ? `${rung.line} ${rung.oddsType}` : `${rung.line}`
  return rung.pOver === null ? name : `${name} · ${percent(rung.pOver)}`
}

function projectionRow(projection: number | null, main: NbaPropRung): NbaProjectionRow | null {
  if (projection === null || main.gap === null) return null
  return {
    projection: oneDecimal(projection),
    gap: signedGap(main.gap),
    pOver: main.pOver === null ? null : percent(main.pOver),
    pUnder: main.pUnder === null ? null : percent(main.pUnder),
  }
}

function card(playerLines: NbaPropLine[]): NbaPropCard {
  const [first] = playerLines
  const rungs = playerLines
    .map(line => ({ line: line.line, oddsType: line.oddsType, pOver: line.pOver, pUnder: line.pUnder, gap: line.gap, flags: line.flags }))
    .sort((a, b) => a.line - b.line)
  const main = mainRung({ rungs })
  const flag = main.flags[0]
  return {
    playerId: first.playerId, playerName: first.playerName, position: first.position, team: first.team, injury: first.injury ?? null,
    rungs, main, also: rungs.filter(rung => rung !== main).map(rungLabel),
    projectionRow: projectionRow(first.projection, main),
    gamesInSample: first.gamesInSample,
    priorMinutes: first.priorMinutes,
    flagText: flag ? nbaPropFlagText(flag) : null,
    recent: first.recent, ...overAgainstStandard(rungs, first.recent),
  }
}

/** One card per player per market with every rung, grouped in `NbaPropMarket` order, cards by name. */
export function nbaPropGroups(lines: NbaPropLine[]): NbaPropGroup[] {
  const groups = new Map<string, Map<number, NbaPropLine[]>>()
  for (const line of lines) {
    const players = groups.get(line.market) ?? new Map<number, NbaPropLine[]>()
    players.set(line.playerId, [...(players.get(line.playerId) ?? []), line])
    groups.set(line.market, players)
  }
  return [...groups.entries()]
    .sort(([left], [right]) => marketRank(left) - marketRank(right))
    .map(([market, players]) => ({
      market,
      cards: [...players.values()].map(card).sort((a, b) => a.playerName.localeCompare(b.playerName)),
    }))
}
