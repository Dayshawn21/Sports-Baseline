import type { NbaPlayerGame, NbaPlayerMarket, NbaPlayerProps, NbaPlayerRung } from '~/types/nba'
import type { FormRow } from '~/utils/nflFormWindow'
import { nbaMarketLabel } from '~/utils/nbaLineOnly'
import { nbaPropFlagText, signedGap } from '~/utils/nbaProps'
import { heroDelta, mainLine, type PlayerHeadChip, type PlayerProjectionHero } from '~/utils/playerProjection'

export type NbaFormWindow = '5' | '10' | 'opp'

export interface NbaFormSample {
  average: number | null
  values: Array<{ value: number, opponentTeam: string | null, gameDate: string }>
}

const SHORT_WINDOW_GAMES = 5
const OPPONENT_BARS = 10

/** 0-based month a new season-year begins: NBA games run October to June, so January to June belong to the season that began the year before. */
export const NBA_SEASON_START_MONTH = 7
/** The first stored NBA season, for the "no earlier games" text. */
export const NBA_HISTORY_FROM_YEAR = 2023

interface PlayerPathOptions {
  date?: string | null
  market?: string | null
}

/** The one place a link to the NBA player page is built; empty options are left off the URL. */
export function nbaPlayerPath(playerId: number, options: PlayerPathOptions = {}): string {
  const params = new URLSearchParams()
  if (options.date) params.set('date', options.date)
  if (options.market) params.set('market', options.market)
  const query = params.toString()
  return query ? `/nba/player/${playerId}?${query}` : `/nba/player/${playerId}`
}

/** The tabs are the response's markets in the order the API sent them, each once. */
export function nbaPlayerTabs(markets: Pick<NbaPlayerMarket, 'market'>[]): string[] {
  return markets.map(item => item.market).filter((market, index, all) => all.indexOf(market) === index)
}

/** The `?market=` tab when it is one of the player's markets, else the first. */
export function nbaSelectedMarket(params: URLSearchParams, markets: string[]): string | null {
  const asked = params.get('market')
  return asked !== null && markets.includes(asked) ? asked : markets[0] ?? null
}

/** Games with a stored value, newest first; a game whose stat was not loaded is left out rather than drawn as zero. */
export function nbaFormSample(games: NbaPlayerGame[]): NbaFormSample {
  const values = games.flatMap(game => game.value === null ? [] : [{ value: game.value, opponentTeam: game.opponent, gameDate: game.gameDate }])
  const average = values.length ? Math.round(values.reduce((sum, item) => sum + item.value, 0) / values.length * 100) / 100 : null
  return { average, values }
}

function windowGames(market: NbaPlayerMarket, window: NbaFormWindow): NbaPlayerGame[] {
  if (window === 'opp') return market.opponentGames.slice(0, OPPONENT_BARS)
  return window === '10' ? market.recent : market.recent.slice(0, SHORT_WINDOW_GAMES)
}

/** How many games in the window had no stat loaded, so the head can say so. */
export function nbaNotLoadedCount(market: NbaPlayerMarket, window: NbaFormWindow): number {
  return windowGames(market, window).filter(game => game.value === null).length
}

/** The chart's reference line: the standard rung, or none, never a guess among alternates. */
export function nbaStandardLine(market: NbaPlayerMarket): number | null {
  return market.lines.find(rung => rung.oddsType === 'standard')?.line ?? null
}

/** The page head's status line: position, team, the opponent when there is a game, and the date. */
export function nbaPlayerStatus(player: Pick<NbaPlayerProps, 'position' | 'team' | 'opponent' | 'date'>): string {
  return [player.position, player.team, player.opponent ? `vs ${player.opponent}` : null, player.date].filter(Boolean).join(' · ')
}

/** A probability as a whole percent; null stays a dash, never zero. */
export function nbaPercentText(probability: number | null): string {
  return probability === null ? '--' : `${Math.round(probability * 100)}%`
}

export interface NbaRungNotes {
  /** One note for the whole table when every rung carries the same flags; null otherwise. */
  shared: string | null
  /** Each rung's own note, only when the rungs differ. */
  perRung: Array<string | null>
}

/** A flag every rung shares (no projection for a player under 20 minutes) is said once, not once per rung. */
export function nbaRungNotes(rungs: NbaPlayerRung[]): NbaRungNotes {
  const texts = rungs.map(rung => rung.flags.length ? rung.flags.map(nbaPropFlagText).join(' · ') : null)
  const first = texts[0] ?? null
  if (first !== null && texts.every(text => text === first)) return { shared: first, perRung: texts.map(() => null) }
  return { shared: null, perRung: texts }
}

/** The rows the shared form helpers take: Last 5, Last 10, and the 10 most recent games against the opponent. */
export function nbaFormRow(market: NbaPlayerMarket, opponent: string | null): FormRow {
  return {
    recentForm: nbaFormSample(market.recent.slice(0, SHORT_WINDOW_GAMES)),
    recentFormLong: nbaFormSample(market.recent),
    opponentHistory: nbaFormSample(market.opponentGames.slice(0, OPPONENT_BARS)),
    opponentTeam: opponent,
  }
}

/** The line the chart draws: the standard rung, never one for double-double, which is a yes or no. */
export function nbaChartLine(market: NbaPlayerMarket): number | null {
  return market.market === 'double_double' ? null : nbaStandardLine(market)
}

const NBA_MIN_PRIOR_GAMES = 10
const NBA_MIN_PRIOR_MINUTES = 20

function nbaMissingReason(market: NbaPlayerMarket): string {
  const flags = new Set(market.lines.flatMap(rung => rung.flags))
  if (flags.has('few_prior_games')) {
    return `No projection: ${market.gamesInSample ?? 0} earlier games, under the ${NBA_MIN_PRIOR_GAMES}-game minimum.`
  }
  if (flags.has('low_minutes') && market.priorMinutes !== null) {
    return `No projection: ${market.priorMinutes.toFixed(1)} minutes a game, under the ${NBA_MIN_PRIOR_MINUTES}-minute floor.`
  }
  return 'No projection for this market today.'
}

/** A modelled market's projection block; null for a line-only market, which has no model to show. */
export function nbaProjectionHero(market: NbaPlayerMarket, modelVersion: string): PlayerProjectionHero | null {
  if (market.kind !== 'modelled') return null
  const value = market.projection === null ? null : market.projection.toFixed(1)
  const line = mainLine(market.lines)
  const facts = [
    { label: 'Model', value: modelVersion },
    { label: 'Sample', value: market.gamesInSample === null ? '--' : `${market.gamesInSample} games` },
  ]
  return {
    label: `Projected ${nbaMarketLabel(market.market).toLowerCase()}`,
    value,
    delta: heroDelta(value, line && { line: String(line.line), gap: line.gap === null ? null : signedGap(line.gap), oddsType: line.oddsType }),
    reason: value === null ? nbaMissingReason(market) : null,
    facts,
  }
}

/** The page head's chips: the model's sample and minutes (the same for every market), then how many markets have lines. */
export function nbaHeadChips(player: Pick<NbaPlayerProps, 'markets'>): PlayerHeadChip[] {
  if (player.markets.length === 0) return []
  const sampled = player.markets.find(market => market.gamesInSample !== null)
  return [
    ...(sampled?.gamesInSample == null ? [] : [{ value: String(sampled.gamesInSample), label: 'Games in sample' }]),
    ...(sampled?.priorMinutes == null ? [] : [{ value: sampled.priorMinutes.toFixed(1), label: 'Avg minutes' }]),
    { value: String(player.markets.length), label: player.markets.length === 1 ? 'Prop market' : 'Prop markets' },
  ]
}

/** Single-stat markets for the joined game log; combos and double-double repeat these. */
export const NBA_LOG_MARKETS = ['points', 'rebounds', 'assists', 'threes_made', 'blocks'] as const
