import type { NflSlateGame } from '~/types/nfl'
import { buildNflPropBoard, type NflBoardCategory, type NflBoardLine } from '~/utils/nflPropBoard'
import type { NflPositionFilter } from '~/utils/nflPositions'
import type { NflPropPeriod } from '~/utils/nflPropPeriods'
import { isTargetsReference } from '~/utils/nflTargets'

export interface NflRankedBoardLine {
  row: NflBoardLine
  /** The line's rank on the week-wide prop board, so a card reads the same on both pages. */
  rank: number | null
}

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
