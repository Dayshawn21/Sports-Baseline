import type { NhlSlateGame } from '~/types/nhl'
import { nhlSlateContext } from '~/utils/nhlContext'
import {
  nhlGameState, nhlMarketCells, nhlPuckDropLabel, nhlTimeLabel, type NhlGameState,
} from '~/utils/nhlGame'

import { latestTime, oddsAsOf } from '~/utils/slatePeriod'

export { parseSlateDate, slateDateLabel } from '~/utils/slateDates'

type NhlSlateContextView = ReturnType<typeof nhlSlateContext>
type NhlGoalieView = NhlSlateContextView['goalies']['away']

const settled = (state: NhlGameState) => state === 'final' || state === 'off'

function goalieTag(team: string, goalie: NhlGoalieView): string | null {
  if (goalie.name === null) return null
  const surname = goalie.name.trim().split(/\s+/).at(-1) ?? goalie.name
  const status = goalie.status === 'Expected' ? ' exp.' : goalie.status === 'Confirmed' ? ' conf.' : ''
  return `${team} G ${surname}${goalie.unresolved ? '?' : ''}${status}`
}

function reportTags({ goalies, injuries }: NhlSlateContextView): string[] {
  const noGoalies = goalies.freshness === 'unavailable'
  const noInjuries = injuries.freshness === 'unavailable'
  if (noGoalies && noInjuries) return ['no ESPN report']
  return [
    ...(goalies.freshness === 'stale' || injuries.freshness === 'stale' ? ['reports stale'] : []),
    ...(noGoalies ? ['no goalie report'] : []),
    ...(noInjuries ? ['no injury report'] : []),
  ]
}

/** Gray slate note tags from the aged ESPN context; none once the game is settled. */
export function nhlNoteTags(context: NhlSlateContextView, state: NhlGameState, away: string, home: string): string[] {
  if (settled(state)) return []
  const { goalies, injuries } = context
  const injuryTag = (team: string, count: number | null) => count ? [`${team} ${count} inj.`] : []
  return [
    goalieTag(away, goalies.away), goalieTag(home, goalies.home),
  ].filter(tag => tag !== null).concat(
    injuryTag(away, injuries.away), injuryTag(home, injuries.home), reportTags(context),
  )
}

/** The favorite's de-vigged market win probability, one decimal; home wins a 50/50 tie. */
export function nhlWinLabel(game: NhlSlateGame, state: NhlGameState): string | null {
  if (game.moneyline === null || settled(state)) return null
  const home = game.moneyline.homeWinProbability * 100
  return home >= 50 ? `${game.homeTeam} ${home.toFixed(1)}%` : `${game.awayTeam} ${(100 - home).toFixed(1)}%`
}

export interface NhlSlateRowCell {
  value: string
  detail: string | null
}

export interface NhlSlateRowModel {
  gameId: number
  state: NhlGameState
  puckDrop: string
  stateLabel: string
  away: { code: string, name: string, score: number | null }
  home: { code: string, name: string, score: number | null }
  puckLine: NhlSlateRowCell
  total: NhlSlateRowCell
  moneyline: NhlSlateRowCell
  /** Favorite's de-vigged market win probability; null without a moneyline. */
  win: string | null
  props: number
  tags: string[]
  /** "as of Tue" while the slate's odds are stale, for a game with a market that is not settled; else null. */
  oddsAge: string | null
}

/** One game as a slate row: book and fetch time stay on the game page, named once in the legend. */
/** `oddsStale` is the period line's stale-odds check. */
export function nhlSlateRow(game: NhlSlateGame, now: Date, oddsStale = false): NhlSlateRowModel {
  const { state, label } = nhlGameState(game, now)
  const [puckLine, total, moneyline] = nhlMarketCells(game).map(({ value, detail }) => ({ value, detail }))
  const context = nhlSlateContext(game.context, game.awayTeam, game.homeTeam, game.startUtc, now)
  return {
    gameId: game.gameId, state, stateLabel: label, puckDrop: nhlPuckDropLabel(game.startUtc),
    away: { code: game.awayTeam, name: game.awayTeamName, score: state === 'final' ? game.awayScore : null },
    home: { code: game.homeTeam, name: game.homeTeamName, score: state === 'final' ? game.homeScore : null },
    puckLine, total, moneyline, win: nhlWinLabel(game, state), props: game.propLineCount,
    tags: nhlNoteTags(context, state, game.awayTeam, game.homeTeam),
    oddsAge: oddsStale && !settled(state) && (game.spread || game.total || game.moneyline)
      ? oddsAsOf(latestTime([game.spread?.fetchedAt, game.total?.fetchedAt, game.moneyline?.fetchedAt]), now.getTime())
      : null,
  }
}

export function nhlSlateSummary(games: readonly NhlSlateGame[]) {
  const times = games.flatMap(game => [game.moneyline, game.spread, game.total])
    .flatMap(market => market === null ? [] : [Date.parse(market.fetchedAt)])
    .filter(Number.isFinite)
  const oddsUpdatedMs = times.length ? Math.max(...times) : null
  return {
    games: games.length,
    propLines: games.reduce((sum, game) => sum + game.propLineCount, 0),
    finals: games.filter(game => game.status === 'completed').length,
    oddsUpdated: oddsUpdatedMs === null ? null : nhlTimeLabel(new Date(oddsUpdatedMs).toISOString()),
    oddsUpdatedMs,
  }
}
