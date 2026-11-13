import type { NbaSplitSide, NbaSplitTeammate, NbaTeammateSplit } from '~/types/nba'

const DOUBLE_DOUBLE = 'double_double'

export interface SplitGameValue {
  gameDate: string
  opponent: string | null
  value: number
}

export interface SplitSideSummary {
  /** Newest first, only games whose stat was loaded. */
  games: SplitGameValue[]
  average: number | null
  /** Games over the line, or double-double yeses; null when there is no line to compare. */
  over: number | null
  notLoaded: number
}

export interface MarketSplit {
  with: SplitSideSummary
  without: SplitSideSummary
  /** Games from before he played for the team, which cannot count as without him. */
  before: number
}

export function parseOutParam(params: URLSearchParams): number | null {
  const value = params.get('out')
  return value !== null && /^\d{1,15}$/.test(value) ? Number(value) : null
}

/** An id from an old link that is not listed out tonight reads as no selection. */
export function activeTeammate(value: number | null, split: NbaTeammateSplit | null): NbaSplitTeammate | null {
  if (value === null || split === null) return null
  return split.teammates.find(teammate => teammate.playerId === value) ?? null
}

export function teammateLabel(teammate: NbaSplitTeammate): string {
  return `${teammate.playerName} (${teammate.status}${teammate.stale ? ', stale report' : ''})`
}

function summarize(split: NbaTeammateSplit, sides: NbaSplitSide[], side: NbaSplitSide, market: string, line: number | null): SplitSideSummary {
  const games: SplitGameValue[] = []
  let notLoaded = 0
  split.games.forEach((game, index) => {
    if (sides[index] !== side) return
    const value = game.values[market] ?? null
    if (value === null) notLoaded += 1
    else games.push({ gameDate: game.gameDate, opponent: game.opponent, value })
  })
  const average = games.length === 0 ? null : games.reduce((sum, game) => sum + game.value, 0) / games.length
  const over = market === DOUBLE_DOUBLE
    ? games.filter(game => game.value >= 1).length
    : line === null ? null : games.filter(game => game.value > line).length
  return { games, average, over, notLoaded }
}

export function marketSplit(split: NbaTeammateSplit, teammate: NbaSplitTeammate, market: string, line: number | null): MarketSplit {
  return {
    with: summarize(split, teammate.sides, 'with', market, line),
    without: summarize(split, teammate.sides, 'without', market, line),
    before: teammate.sides.filter(side => side === 'before').length,
  }
}

export const SPLIT_BAR_LIMIT = 10
export const SMALL_SPLIT_SAMPLE = 5

function oneDecimal(value: number): string {
  return Number.isInteger(value) ? String(value) : value.toFixed(1)
}

/** One side's line of the split, e.g. `6 games · 27.1 avg · 5 over 24.5`, or `2 of 6 yes` for double-double. */
export function splitSideText(side: SplitSideSummary, market: string, line: number | null): string {
  const count = side.games.length
  if (count === 0) return 'No games'
  if (market === DOUBLE_DOUBLE) return `${side.over ?? 0} of ${count} yes`
  const games = `${count} game${count === 1 ? '' : 's'}`
  const average = side.average === null ? null : `${oneDecimal(side.average)} avg`
  const over = side.over === null || line === null ? null : `${side.over} over ${line}`
  return [games, average, over].filter(Boolean).join(' · ')
}
