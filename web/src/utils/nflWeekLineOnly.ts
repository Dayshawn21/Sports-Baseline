import type { NflLineOnlyBoardGame, NflPropGame, NflSlateGame } from '~/types/nfl'
import { LINE_ONLY_MARKETS, lineOnlyGroups, type NflLineOnlyGroup } from '~/utils/nflLineOnly'
import type { NflPositionFilter } from '~/utils/nflPositions'
import { isUpcomingGame } from '~/utils/nflPropBoard'

export interface NflWeekLineOnlyCategory {
  market: string
  count: number
  games: Array<{ game: NflPropGame, group: NflLineOnlyGroup }>
}

export function availableNflPropGames(modelled: NflSlateGame[], lineOnly: NflLineOnlyBoardGame[], now = new Date()): NflPropGame[] {
  const games = new Map<number, NflPropGame>()
  for (const game of [...modelled, ...lineOnly]) {
    if (game.lines.length && isUpcomingGame(game, now)) games.set(game.gameId, game)
  }
  return [...games.values()].sort((a, b) => (a.startUtc ?? '').localeCompare(b.startUtc ?? '') || a.gameId - b.gameId)
}

export function nflWeekLineOnlyCategories(games: NflLineOnlyBoardGame[], position: NflPositionFilter, gameId: number | null, now = new Date()): NflWeekLineOnlyCategory[] {
  const categories = new Map<string, NflWeekLineOnlyCategory>()
  for (const game of games) {
    if (!isUpcomingGame(game, now) || (gameId !== null && game.gameId !== gameId)) continue
    for (const group of lineOnlyGroups(game.lines, position)) {
      const category = categories.get(group.market) ?? { market: group.market, count: 0, games: [] }
      category.games.push({ game, group })
      category.count += group.rows.length
      categories.set(group.market, category)
    }
  }
  return LINE_ONLY_MARKETS.flatMap(market => categories.has(market) ? [categories.get(market)!] : [])
}
