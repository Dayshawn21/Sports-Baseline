import type { NflLineOnlyBoardGame, NflPropGame, NflSlateGame } from '~/types/nfl'
import { LINE_ONLY_MARKETS, lineOnlyGroups, type NflLineOnlyGroup } from '~/utils/nflLineOnly'
import type { NflPositionFilter } from '~/utils/nflPositions'
import { filterNflBoardCategories, isUpcomingGame, type NflBoardCategory } from '~/utils/nflPropBoard'
import { gameSideTeam, playerOptions, playerSelected, teamMatches } from '~/utils/propFilters'

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

export function nflWeekLineOnlyCategories(games: NflLineOnlyBoardGame[], position: NflPositionFilter, gameIds: readonly number[], now = new Date()): NflWeekLineOnlyCategory[] {
  const categories = new Map<string, NflWeekLineOnlyCategory>()
  for (const game of games) {
    if (!isUpcomingGame(game, now) || (gameIds.length > 0 && !gameIds.includes(game.gameId))) continue
    for (const group of lineOnlyGroups(game.lines, position)) {
      const category = categories.get(group.market) ?? { market: group.market, count: 0, games: [] }
      category.games.push({ game, group })
      category.count += group.rows.length
      categories.set(group.market, category)
    }
  }
  return LINE_ONLY_MARKETS.flatMap(market => categories.has(market) ? [categories.get(market)!] : [])
}

/** Narrows each game's rows and drops what empties, reading a provider team code as its game's code. */
export function filterNflWeekLineOnly(categories: NflWeekLineOnlyCategory[], players: readonly string[], team: string): NflWeekLineOnlyCategory[] {
  return categories.flatMap(category => {
    const games = category.games.flatMap(({ game, group }) => {
      const rows = group.rows.filter(row => playerSelected(row.playerName, players) && teamMatches(gameSideTeam(row.team, game), team))
      return rows.length ? [{ game, group: { ...group, rows } }] : []
    })
    return games.length ? [{ ...category, games, count: games.reduce((total, item) => total + item.group.rows.length, 0) }] : []
  })
}

/** The picker lists players under the current position, games and team; hidden review lines stay out until shown. */
export function nflBoardPlayerOptions(categories: NflBoardCategory[], other: NflWeekLineOnlyCategory[], team: string, players: readonly string[], showAll: boolean): string[] {
  return playerOptions([
    ...filterNflBoardCategories(categories, [], team).flatMap(item => [...item.rateable.map(entry => entry.row.playerName), ...(showAll ? item.other.map(row => row.playerName) : [])]),
    ...filterNflWeekLineOnly(other, [], team).flatMap(category => category.games.flatMap(entry => entry.group.rows.map(row => row.playerName))),
  ], players)
}
