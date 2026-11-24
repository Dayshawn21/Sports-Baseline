import type {
  NbaBoardRecentGame, NbaInjury, NbaInjuryReport, NbaLineOnlyRecent, NbaPropBoardGame, NbaPropBoardResponse,
  NbaPropBoardWireGame, NbaPropBoardWireResponse,
} from '~/types/nba'

/** The API's `injury_index`: linked entries whose ESPN team, when known, is the game team. */
function injuryIndex(report: NbaInjuryReport): Map<string, NbaInjury> {
  const index = new Map<string, NbaInjury>()
  for (const entry of report.injuries) {
    if (entry.playerId !== null && (entry.athleteTeam === null || entry.athleteTeam === entry.team)) {
      index.set(`${entry.playerId}:${entry.team}`, entry)
    }
  }
  return index
}

function recentFor(games: NbaBoardRecentGame[] | undefined, market: string): NbaLineOnlyRecent[] {
  return (games ?? []).map(({ gameDate, opponent, values }) => ({ gameDate, opponent, value: values[market] ?? null }))
}

type WireLine = NbaPropBoardWireGame['lineOnlyLines'][number]

function expandGame(game: NbaPropBoardWireGame): NbaPropBoardGame {
  const { playerRecent, ...rest } = game
  const injuries = injuryIndex(game.injuryReport)
  const recent = new Map((playerRecent ?? []).map(player => [player.playerId, player.games]))
  // An older API sent each line in full and no `playerRecent`; keep its values.
  const expand = <L extends WireLine>(line: L) => playerRecent === undefined
    ? { ...line, recent: line.recent ?? [], injury: line.injury ?? null }
    : {
        ...line,
        recent: recentFor(recent.get(line.playerId), line.market),
        injury: line.team === null ? null : injuries.get(`${line.playerId}:${line.team}`) ?? null,
      }
  return { ...rest, lines: rest.lines.map(expand), lineOnlyLines: rest.lineOnlyLines.map(expand) }
}

/** The board with each line's recent games and injury rebuilt, as the game page sends them. */
export function nbaExpandPropBoard(board: NbaPropBoardWireResponse): NbaPropBoardResponse {
  return { ...board, games: board.games.map(expandGame) }
}
