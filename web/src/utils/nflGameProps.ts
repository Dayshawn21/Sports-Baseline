import type { NflSlateGame } from '~/types/nfl'
import { buildNflPropBoard, nflLineTeam, type NflBoardCategory, type NflBoardLine, type NflRankedBoardLine } from '~/utils/nflPropBoard'
import type { NflPositionFilter } from '~/utils/nflPositions'
import type { NflPropPeriod } from '~/utils/nflPropPeriods'
import { isTargetsReference } from '~/utils/nflTargets'
import { playerNameMatches, teamMatches, type GamePropFilter } from '~/utils/propFilters'

export interface NflGamePropCategory {
  /** The week-wide category, whose reference line scores every card's edge share. */
  category: NflBoardCategory
  rateable: NflRankedBoardLine[]
  other: NflBoardLine[]
}

/**
 * The board as it stood just before this game's kickoff. The prop board drops a game once it
 * starts, so a finished game's page would otherwise lose its cards; reading the board as of
 * kickoff keeps the ranks it last showed.
 */
export function gameBoardAsOf(game: Pick<NflSlateGame, 'startUtc'>, now: Date): Date {
  const kickoff = game.startUtc === null ? Number.NaN : Date.parse(game.startUtc)
  return Number.isNaN(kickoff) ? now : new Date(Math.min(now.getTime(), kickoff - 1))
}

/** One game's props, grouped by market in prop-board order, with ranks from the week-wide board. */
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
      rateable: category.rateable.flatMap((row, index) => inView(row) ? [{ row, rank: isTargetsReference(row.market) ? null : index + 1 }] : []),
      other: category.other.filter(inView),
    }))
    .filter(item => item.rateable.length > 0 || item.other.length > 0)
}

/** Ranks are already the board's, so narrowing a game's rows cannot renumber them. */
export function filterNflGameProps(categories: NflGamePropCategory[], filter: GamePropFilter): NflGamePropCategory[] {
  const keep = (row: NflBoardLine) => playerNameMatches(row.playerName, filter.q) && teamMatches(nflLineTeam(row), filter.team)
  return categories.map(item => ({ ...item, rateable: item.rateable.filter(entry => keep(entry.row)), other: item.other.filter(keep) }))
}
