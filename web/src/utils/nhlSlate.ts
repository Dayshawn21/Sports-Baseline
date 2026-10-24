import type { NhlSlateGame } from '~/types/nhl'
import { nhlGameState, nhlMarketCells, nhlMarketProbability, nhlPuckDropLabel, nhlTimeLabel } from '~/utils/nhlGame'

export { parseSlateDate, slateDateLabel } from '~/utils/slateDates'

export function nhlSlateRow(game: NhlSlateGame, now: Date) {
  const { state, label } = nhlGameState(game, now)
  const [puckLine, total, moneyline] = nhlMarketCells(game)
  return {
    gameId: game.gameId, state, stateLabel: label, puckDrop: nhlPuckDropLabel(game.startUtc),
    away: { code: game.awayTeam, name: game.awayTeamName, score: state === 'final' ? game.awayScore : null },
    home: { code: game.homeTeam, name: game.homeTeamName, score: state === 'final' ? game.homeScore : null },
    puckLine, total, moneyline, probability: nhlMarketProbability(game), props: game.propLineCount,
  }
}

export function nhlSlateSummary(games: readonly NhlSlateGame[]) {
  const times = games.flatMap(game => [game.moneyline, game.spread, game.total])
    .flatMap(market => market === null ? [] : [Date.parse(market.fetchedAt)])
    .filter(Number.isFinite)
  return {
    games: games.length,
    propLines: games.reduce((sum, game) => sum + game.propLineCount, 0),
    finals: games.filter(game => game.status === 'completed').length,
    oddsUpdated: times.length ? nhlTimeLabel(new Date(Math.max(...times)).toISOString(), true) : null,
  }
}
