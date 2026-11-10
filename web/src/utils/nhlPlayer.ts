import type { NhlPlayerGame, NhlPlayerInjury, NhlPlayerMarket, NhlPlayerProps } from '~/types/nhl'
import type { NhlContextSource } from '~/types/nhlContext'
import type { FormRow, FormWindow } from '~/utils/nflFormWindow'
import { nhlTimeLabel } from '~/utils/nhlGame'
import { nhlMarketLabel, nhlPropLineLabel } from '~/utils/nhlLineOnly'
import { latestTime } from '~/utils/playerPage'
import { nhlGapLabel, nhlProjectionNote } from '~/utils/nhlProjection'
import { nhlContextSource, nhlGoalieLabel } from '~/utils/nhlContext'
import { heroDelta, mainLine, type PlayerHeadChip, type PlayerProjectionHero } from '~/utils/playerProjection'

export interface NhlFormSample {
  average: number | null
  values: Array<{ value: number, opponentTeam: string | null, gameDate: string }>
}

const SHORT_WINDOW_GAMES = 5
const OPPONENT_BARS = 10
const GOALIE_MARKETS = new Set(['goalie_saves', 'goals_allowed'])

/** 0-based month a new season-year begins: NHL games run October to June, so January to June belong to the season that began the year before. */
export const NHL_SEASON_START_MONTH = 7
/** The first stored NHL season, for the "no earlier games" text. */
export const NHL_HISTORY_FROM_YEAR = 2023

interface PlayerPathOptions {
  date?: string | null
  market?: string | null
}

/** The one place a link to the NHL player page is built; empty options are left off the URL. */
export function nhlPlayerPath(playerId: number, options: PlayerPathOptions = {}): string {
  const params = new URLSearchParams()
  if (options.date) params.set('date', options.date)
  if (options.market) params.set('market', options.market)
  const query = params.toString()
  return query ? `/nhl/player/${playerId}?${query}` : `/nhl/player/${playerId}`
}

/** The tabs are the response's markets in the order the API sent them, each once. */
export function nhlPlayerTabs(markets: Pick<NhlPlayerMarket, 'market'>[]): string[] {
  return markets.map(item => item.market).filter((market, index, all) => all.indexOf(market) === index)
}

/** The `?market=` tab when it is one of the player's markets, else the first. */
export function nhlSelectedMarket(params: URLSearchParams, markets: string[]): string | null {
  const asked = params.get('market')
  return asked !== null && markets.includes(asked) ? asked : markets[0] ?? null
}

/** Games with a stored value, newest first; a game whose stat was not loaded is left out rather than drawn as zero. */
export function nhlFormSample(games: NhlPlayerGame[]): NhlFormSample {
  const values = games.flatMap(game => game.value === null ? [] : [{ value: game.value, opponentTeam: game.opponent, gameDate: game.gameDate }])
  const average = values.length ? Math.round(values.reduce((sum, item) => sum + item.value, 0) / values.length * 100) / 100 : null
  return { average, values }
}

function windowGames(market: NhlPlayerMarket, window: FormWindow): NhlPlayerGame[] {
  if (window === 'opp') return market.opponentGames.slice(0, OPPONENT_BARS)
  return window === '10' ? market.recent : market.recent.slice(0, SHORT_WINDOW_GAMES)
}

/** How many games in the window had no stat loaded, so the head can say so. */
export function nhlNotLoadedCount(market: NhlPlayerMarket, window: FormWindow): number {
  return windowGames(market, window).filter(game => game.value === null).length
}

/** The chart's reference line: the standard rung, or none, never a guess among alternates. */
export function nhlChartLine(market: NhlPlayerMarket): number | null {
  return market.lines.find(rung => rung.oddsType === 'standard')?.line ?? null
}

/** The rows the shared form helpers take: Last 5, Last 10, and the 10 most recent games against the opponent. */
export function nhlFormRow(market: NhlPlayerMarket, opponent: string | null): FormRow {
  return {
    recentForm: nhlFormSample(market.recent.slice(0, SHORT_WINDOW_GAMES)),
    recentFormLong: nhlFormSample(market.recent),
    opponentHistory: nhlFormSample(market.opponentGames.slice(0, OPPONENT_BARS)),
    opponentTeam: opponent,
  }
}

/** Goalie samples count games the goalie started, which the chart says so a short or old sample is not misread. */
export function nhlSampleNote(market: Pick<NhlPlayerMarket, 'market'>): string | null {
  return GOALIE_MARKETS.has(market.market) ? 'Started games only' : null
}

/** The page head's status line: position, team, the opponent when there is a game, and the date. */
export function nhlPlayerStatus(player: Pick<NhlPlayerProps, 'position' | 'team' | 'opponent' | 'date'>): string {
  return [player.position, player.team, player.opponent ? `vs ${player.opponent}` : null, player.date].filter(Boolean).join(' · ')
}

/** The injury report as the shared context helpers take it; the player endpoint's block has no source field of its own. */
export function nhlPlayerInjuryReport(injury: NhlPlayerInjury): NhlContextSource {
  return { source: 'ESPN', fetchedAt: injury.fetchedAt, sourceTimestamp: injury.sourceTimestamp, freshness: injury.freshness }
}

/** A market's projection block: the 20-game reference number, or the reason it is missing. */
export function nhlProjectionHero(market: NhlPlayerMarket): PlayerProjectionHero {
  const { projection } = market
  const value = projection.value === null ? null : projection.value.toFixed(1)
  const line = mainLine(market.lines)
  const note = nhlProjectionNote(projection)
  return {
    label: `Projected ${nhlMarketLabel(market.market).toLowerCase()}`,
    value,
    delta: heroDelta(value, line && { line: nhlPropLineLabel(market.market, line.line), gap: line.gap === null ? null : nhlGapLabel(line.gap), oddsType: line.oddsType }),
    reason: value === null ? `No projection: ${note === null ? 'not served for this market today' : note.charAt(0).toLowerCase() + note.slice(1)}.` : note,
    facts: [
      { label: 'Model', value: projection.modelVersion },
      { label: 'Sample', value: `${projection.gamesInSample} games` },
    ],
  }
}

const TOI_GAMES = 10

/** The page head's chips: the 20-game sample, average TOI when a time-on-ice line carries the player's recent games, then the market count. */
export function nhlHeadChips(player: Pick<NhlPlayerProps, 'markets'>): PlayerHeadChip[] {
  if (player.markets.length === 0) return []
  const games = Math.max(...player.markets.map(market => market.projection.gamesInSample))
  const toi = player.markets.find(market => market.market === 'time_on_ice')?.recent
    .slice(0, TOI_GAMES).flatMap(game => game.value === null ? [] : [game.value]) ?? []
  return [
    ...(games > 0 ? [{ value: String(games), label: 'Games in sample' }] : []),
    ...(toi.length > 0 ? [{ value: (toi.reduce((sum, value) => sum + value, 0) / toi.length).toFixed(1), label: `Avg TOI, last ${toi.length}` }] : []),
    { value: String(player.markets.length), label: player.markets.length === 1 ? 'Prop market' : 'Prop markets' },
  ]
}

/** "BOS goalie: Name, Confirmed" for the other team's starter; null when the report is unavailable or the opponent is unknown. */
export function nhlOpposingGoalieTag(player: Pick<NhlPlayerProps, 'goalies' | 'opponent' | 'game'>, now: Date): string | null {
  const goalies = player.goalies
  if (goalies === null || player.opponent === null) return null
  const freshness = nhlContextSource(goalies, player.game?.startUtc ?? null, now).freshness
  if (freshness === 'unavailable') return null
  const side = goalies.away.team === player.opponent ? goalies.away : goalies.home.team === player.opponent ? goalies.home : null
  if (side === null) return null
  const label = nhlGoalieLabel(side, true)
  return `${side.team} goalie: ${label.name ? `${label.name}, ` : ''}${label.status}${freshness === 'stale' ? ' (stale)' : ''}`
}

/** Skater stats first, then goalie stats, for the joined game log. */
export const NHL_LOG_MARKETS = [
  'goals', 'assists', 'points', 'shots_on_goal', 'power_play_points', 'blocked_shots', 'hits', 'faceoffs_won', 'plus_minus',
  'time_on_ice', 'goalie_saves', 'goals_allowed',
] as const

function isLogMarket(market: string): market is (typeof NHL_LOG_MARKETS)[number] {
  return (NHL_LOG_MARKETS as readonly string[]).includes(market)
}

export function nhlLogLabel(market: string): string {
  return isLogMarket(market) ? nhlMarketLabel(market) : market
}

/** A game log cell: TOI to one decimal, plus/minus signed, else the count. */
export function nhlLogValue(market: string, value: number | null): string {
  if (value === null) return '--'
  if (market === 'time_on_ice') return value.toFixed(1)
  if (market === 'plus_minus' && value > 0) return `+${value}`
  return String(value)
}

/** The page footer: when the lines and the injury report were last read, and which P(over) fit is served. */
export function nhlPlayerFooter(player: Pick<NhlPlayerProps, 'markets' | 'injury' | 'overProbabilityVersion'>): string {
  const lines = latestTime(player.markets.flatMap(market => market.lines.map(rung => rung.fetchedAt)))
  return [
    lines === null ? 'No PrizePicks lines stored.' : `PrizePicks lines as of ${nhlTimeLabel(lines, true)}.`,
    player.injury.fetchedAt === null ? 'No ESPN injury report loaded.' : `ESPN injury report as of ${nhlTimeLabel(player.injury.fetchedAt, true)}.`,
    player.overProbabilityVersion === null ? null : `P(over) from ${player.overProbabilityVersion}.`,
  ].filter(Boolean).join(' ')
}
