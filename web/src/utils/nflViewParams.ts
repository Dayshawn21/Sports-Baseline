import { NFL_POSITION_OPTIONS, type NflPositionFilter } from '~/utils/nflPositions'
import { ALL, parsePlayerQuery, parseTeamFilter, withPropFilters } from '~/utils/propFilters'

export interface NflBoardView {
  /** Season and week are both null (follow the current week) or both set. */
  season: number | null
  week: number | null
  position: NflPositionFilter
  market: string | null
  /** A game id, or 'all'. */
  game: string
  showAll: boolean
  q: string
  team: string
}

export interface NflGameView {
  position: NflPositionFilter
  showAll: boolean
}

export const DEFAULT_BOARD_VIEW: NflBoardView = { season: null, week: null, position: 'all', market: null, game: 'all', showAll: false, q: '', team: ALL }

function integerIn(value: string | null, min: number, max: number): number | null {
  if (value === null || !/^\d+$/.test(value)) return null
  const number = Number(value)
  return number >= min && number <= max ? number : null
}

function positionParam(value: string | null): NflPositionFilter {
  return NFL_POSITION_OPTIONS.find(option => option.value === value)?.value ?? 'all'
}

function marketParam(value: string | null): string | null {
  return value !== null && /^[a-z0-9_]{1,64}$/.test(value) ? value : null
}

export function parseBoardView(params: URLSearchParams): NflBoardView {
  const season = integerIn(params.get('season'), 2000, 2100)
  const week = integerIn(params.get('week'), 1, 25)
  const pinned = season !== null && week !== null
  const game = integerIn(params.get('game'), 1, Number.MAX_SAFE_INTEGER)
  return {
    season: pinned ? season : null,
    week: pinned ? week : null,
    position: positionParam(params.get('position')),
    market: marketParam(params.get('market')),
    game: game === null ? 'all' : String(game),
    showAll: params.get('all') === '1',
    q: parsePlayerQuery(params.get('q')),
    team: parseTeamFilter(params.get('team')),
  }
}

export function boardViewSearch(view: NflBoardView): URLSearchParams {
  const params = new URLSearchParams()
  if (view.season !== null && view.week !== null) {
    params.set('season', String(view.season))
    params.set('week', String(view.week))
  }
  if (view.position !== 'all') params.set('position', view.position)
  if (view.market !== null) params.set('market', view.market)
  if (view.game !== 'all') params.set('game', view.game)
  if (view.showAll) params.set('all', '1')
  return withPropFilters(params, { q: view.q, team: view.team })
}

export function parseGameView(params: URLSearchParams): NflGameView {
  return { position: positionParam(params.get('position')), showAll: params.get('all') === '1' }
}

export function gameViewSearch(view: NflGameView): URLSearchParams {
  const params = new URLSearchParams()
  if (view.position !== 'all') params.set('position', view.position)
  if (view.showAll) params.set('all', '1')
  return params
}
