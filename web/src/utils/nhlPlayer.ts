import type { NhlPlayerGame, NhlPlayerInjury, NhlPlayerMarket, NhlPlayerProps } from '~/types/nhl'
import type { NhlContextSource } from '~/types/nhlContext'
import type { FormRow, FormWindow } from '~/utils/nflFormWindow'

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
