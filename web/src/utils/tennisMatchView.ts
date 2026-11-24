import type { MatchDetail, PropLine } from '~/types/tennis'
import { parseMatchId } from '~/utils/tennisMatch'

export interface MatchView {
  tab: 'analysis' | 'props'
  source: 'prizepicks' | 'dk'
  player: number | 'all'
  market: string
}

export function readMatchView(params: URLSearchParams, detail: {
  p1: Pick<MatchDetail['p1'], 'playerId'>; p2: Pick<MatchDetail['p2'], 'playerId'>,
}, admin: boolean): MatchView {
  const requestedSource = params.get('source') ?? 'prizepicks'
  const source = admin && requestedSource === 'dk' ? requestedSource : 'prizepicks'
  const player = parseMatchId(params.get('player') ?? undefined)
  const market = params.get('market') ?? 'all'
  return {
    tab: params.get('tab') === 'props' ? 'props' : 'analysis',
    source,
    player: player === detail.p1.playerId || player === detail.p2.playerId ? player : 'all',
    market: /^[a-z0-9_]{1,100}$/.test(market) ? market : 'all',
  }
}

export function updateMatchView(params: URLSearchParams, patch: Partial<MatchView>): URLSearchParams {
  const next = new URLSearchParams(params)
  const defaults: MatchView = { tab: 'analysis', source: 'prizepicks', player: 'all', market: 'all' }
  for (const key of Object.keys(patch) as Array<keyof MatchView>) {
    const value = patch[key]
    if (value == null || value === defaults[key]) next.delete(key)
    else next.set(key, String(value))
  }
  return next
}

export function propMatchPath(line: PropLine): string | null {
  if (line.matchId == null || !Number.isSafeInteger(line.matchId) || line.matchId <= 0) return null
  const query = new URLSearchParams({ tab: 'props' })
  const source = line.source.toLowerCase()
  const knownSource = source === 'prizepicks' ? 'prizepicks' : source === 'dk' || source === 'draftkings' ? 'dk' : null
  if (knownSource != null) {
    query.set('source', knownSource)
    query.set('market', line.statType.trim().toLowerCase().replace(/[\s-]+/g, '_'))
    if (line.playerId != null) query.set('player', String(line.playerId))
  }
  return `/tennis/match/${line.matchId}?${query}`
}

/** The match page's props tab as the viewer has it filtered, for a link back from the player page. */
export function matchPropsPath(matchId: number, view: Pick<MatchView, 'source' | 'player' | 'market'>): string {
  const query = new URLSearchParams({ tab: 'props' })
  if (view.source !== 'prizepicks') query.set('source', view.source)
  if (view.player !== 'all') query.set('player', String(view.player))
  if (view.market !== 'all') query.set('market', view.market)
  return `/tennis/match/${matchId}?${query}`
}
