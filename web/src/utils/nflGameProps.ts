import type { NflSlateGame } from '~/types/nfl'
import { buildNflPropBoard, nflLineTeam, type NflBoardCategory, type NflBoardLine } from '~/utils/nflPropBoard'
import type { NflPositionFilter } from '~/utils/nflPositions'
import type { NflPropPeriod } from '~/utils/nflPropPeriods'
import { playerOptions, playerSelected, teamMatches, type GamePropFilter } from '~/utils/propFilters'

export interface NflGamePropCategory {
  /** The week-wide category, whose reference line scores every card's edge share. */
  category: NflBoardCategory
  rateable: NflBoardLine[]
  other: NflBoardLine[]
}

/**
 * The board as it stood just before this game's kickoff. The prop board drops a game once it
 * starts, so a finished game's page would otherwise lose its cards; reading the board as of
 * kickoff keeps the rows it last showed.
 */
export function gameBoardAsOf(game: Pick<NflSlateGame, 'startUtc'>, now: Date): Date {
  const kickoff = game.startUtc === null ? Number.NaN : Date.parse(game.startUtc)
  return Number.isNaN(kickoff) ? now : new Date(Math.min(now.getTime(), kickoff - 1))
}

/** One game's props, grouped by market in prop-board order, scored against the week-wide board's reference lines. */
export function nflGameProps(
  games: NflSlateGame[],
  gameId: number,
  position: NflPositionFilter,
  period: NflPropPeriod,
  now = new Date(),
): NflGamePropCategory[] {
  const game = games.find(item => item.gameId === gameId)
  if (!game) return []
  const inView = (row: NflBoardLine) => row.gameId === gameId && row.segment === period
  return buildNflPropBoard(games, position, gameBoardAsOf(game, now))
    .map(category => ({
      category,
      rateable: category.rateable.filter(inView),
      other: category.other.filter(inView),
    }))
    .filter(item => item.rateable.length > 0 || item.other.length > 0)
}

export function filterNflGameProps(categories: NflGamePropCategory[], filter: GamePropFilter): NflGamePropCategory[] {
  const keep = (row: NflBoardLine) => playerSelected(row.playerName, filter.players) && teamMatches(nflLineTeam(row), filter.team)
  return categories.map(item => ({ ...item, rateable: item.rateable.filter(keep), other: item.other.filter(keep) }))
}

/** The picker lists players on the chosen side from both tables; hidden alternate lines stay out until shown. */
export function nflGamePlayerOptions(categories: NflGamePropCategory[], otherNames: ReadonlyArray<string>, filter: GamePropFilter, showAll: boolean): string[] {
  const modelled = filterNflGameProps(categories, { ...filter, players: [] })
    .flatMap(item => [...item.rateable.map(row => row.playerName), ...(showAll ? item.other.map(row => row.playerName) : [])])
  return playerOptions([...modelled, ...otherNames], filter.players)
}
