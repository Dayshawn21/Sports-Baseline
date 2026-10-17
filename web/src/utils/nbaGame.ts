import type { NbaSlateGame } from '~/types/nba'
import { spreadLabel } from '~/utils/nflGameModel'
import { fmtAmerican } from '~/utils/odds'

export { parseGameId } from '~/utils/nflGame'

const NOT_STORED: NbaMarketCell = { value: '--', detail: 'Not stored' }

export interface NbaMarketCell {
  value: string
  detail: string
}

export interface NbaGameMarket {
  spread: NbaMarketCell
  winProbability: NbaMarketCell
  total: NbaMarketCell
}

function spreadCell(game: NbaSlateGame): NbaMarketCell {
  if (game.spread === null) return NOT_STORED
  const { homeLine, homeOdds, awayOdds, book } = game.spread
  // The favorite's price leads; a pick'em leads with home.
  const prices = homeLine <= 0 ? [homeOdds, awayOdds] : [awayOdds, homeOdds]
  return {
    value: spreadLabel(homeLine, game.homeTeam, game.awayTeam),
    detail: `${prices.map(fmtAmerican).join(' / ')} · ${book}`,
  }
}

function winProbabilityCell(game: NbaSlateGame): NbaMarketCell {
  if (game.moneyline === null) return NOT_STORED
  const { homeOdds, awayOdds, homeWinProbability, book } = game.moneyline
  const homeLeads = homeWinProbability >= 0.5
  const team = homeLeads ? game.homeTeam : game.awayTeam
  const probability = homeLeads ? homeWinProbability : 1 - homeWinProbability
  const home = `${game.homeTeam} ${fmtAmerican(homeOdds)}`
  const away = `${game.awayTeam} ${fmtAmerican(awayOdds)}`
  return {
    value: `${team} ${(probability * 100).toFixed(1)}%`,
    detail: `${homeLeads ? `${home} / ${away}` : `${away} / ${home}`} de-vigged · ${book}`,
  }
}

function totalCell(game: NbaSlateGame): NbaMarketCell {
  if (game.total === null) return NOT_STORED
  const { line, overOdds, underOdds, book } = game.total
  return { value: line.toFixed(1), detail: `o ${fmtAmerican(overOdds)} / u ${fmtAmerican(underOdds)} · ${book}` }
}

/** The game page's market row; each market names its own book. Null when none is stored. */
export function nbaGameMarket(game: NbaSlateGame): NbaGameMarket | null {
  if (game.moneyline === null && game.spread === null && game.total === null) return null
  return { spread: spreadCell(game), winProbability: winProbabilityCell(game), total: totalCell(game) }
}
