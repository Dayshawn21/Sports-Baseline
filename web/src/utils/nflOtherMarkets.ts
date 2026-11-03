import type { NflHistorySample, NflOtherMarket, NflOtherMarketGame, NflOtherMarkets } from '~/types/nfl'
import { LINE_ONLY_MARKETS } from '~/utils/nflLineOnly'
import type { FormRow, FormWindow } from '~/utils/nflFormWindow'

export interface PlayerTab {
  market: string
  kind: 'model' | 'other'
}

const RECENT_SHORT = 5

/** Games with a stored value, newest first; a game whose stat was not loaded is left out rather than drawn as zero. */
export function otherMarketSample(games: NflOtherMarketGame[]): NflHistorySample {
  const values = games.flatMap(game => game.value === null ? [] : [{ value: game.value, opponentTeam: game.opponent, gameDate: game.gameDate }])
  const average = values.length ? Math.round(values.reduce((sum, item) => sum + item.value, 0) / values.length * 100) / 100 : null
  return { average, values }
}

export function otherMarketFormRow(market: NflOtherMarket, opponent: NflOtherMarkets['opponent']): FormRow {
  return {
    recentForm: otherMarketSample(market.recent.slice(0, RECENT_SHORT)),
    recentFormLong: otherMarketSample(market.recent),
    opponentHistory: otherMarketSample(market.opponentGames),
    opponentTeam: opponent,
  }
}

function windowGames(market: NflOtherMarket, window: FormWindow): NflOtherMarketGame[] {
  if (window === 'opp') return market.opponentGames
  return window === '10' ? market.recent : market.recent.slice(0, RECENT_SHORT)
}

/** How many games in the window had no stat loaded, so the head can say so. */
export function notLoadedCount(market: NflOtherMarket, window: FormWindow): number {
  return windowGames(market, window).filter(game => game.value === null).length
}

/** The chart's reference line: the standard rung, or none, never a guess among alternates. */
export function standardLine(market: NflOtherMarket): number | null {
  return market.lines.find(rung => rung.oddsType === 'standard')?.line ?? null
}

/** Model tabs first, then the line-only markets in board order; a market already a model tab is not listed twice. */
export function playerTabs(modelMarkets: string[], otherMarkets: string[]): PlayerTab[] {
  const rank = (market: string) => { const index = LINE_ONLY_MARKETS.indexOf(market); return index === -1 ? LINE_ONLY_MARKETS.length : index }
  const others = otherMarkets.filter((market, index) => !modelMarkets.includes(market) && otherMarkets.indexOf(market) === index)
    .sort((a, b) => rank(a) - rank(b))
  return [...modelMarkets.map(market => ({ market, kind: 'model' as const })), ...others.map(market => ({ market, kind: 'other' as const }))]
}
