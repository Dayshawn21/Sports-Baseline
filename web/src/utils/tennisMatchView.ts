import type { MatchDetail, PropLine } from '~/types/tennis'
import { parseMatchId } from '~/utils/tennisMatch'

export interface MatchView {
  tab: 'analysis' | 'props'
  source: 'prizepicks' | 'dk' | 'bet'
  player: number | 'all'
  market: string
  prop: number | null
}

export function readMatchView(params: URLSearchParams, detail: {
  p1: Pick<MatchDetail['p1'], 'playerId'>; p2: Pick<MatchDetail['p2'], 'playerId'>,
}, admin: boolean): MatchView {
  const requestedSource = params.get('source') ?? 'prizepicks'
  const source = admin && (requestedSource === 'dk' || requestedSource === 'bet') ? requestedSource : 'prizepicks'
  const player = parseMatchId(params.get('player') ?? undefined)
  const market = params.get('market') ?? 'all'
  return {
    tab: params.get('tab') === 'props' ? 'props' : 'analysis',
    source,
    player: player === detail.p1.playerId || player === detail.p2.playerId ? player : 'all',
    market: /^[a-z0-9_]{1,100}$/.test(market) ? market : 'all',
    prop: requestedSource === source ? parseMatchId(params.get('prop') ?? undefined) : null,
  }
}

export function updateMatchView(params: URLSearchParams, patch: Partial<MatchView>): URLSearchParams {
  const next = new URLSearchParams(params)
  const defaults: MatchView = { tab: 'analysis', source: 'prizepicks', player: 'all', market: 'all', prop: null }
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
  const knownSource = source === 'prizepicks' ? 'prizepicks' : source === 'dk' || source === 'draftkings'
    ? 'dk' : source === 'bet' || source === 'bet365' ? 'bet' : null
  if (knownSource != null) {
    query.set('source', knownSource)
    query.set('market', line.statType.trim().toLowerCase().replace(/[\s-]+/g, '_'))
    if (line.playerId != null) query.set('player', String(line.playerId))
    if (Number.isSafeInteger(line.id) && line.id > 0) query.set('prop', String(line.id))
  }
  return `/tennis/match/${line.matchId}?${query}`
}
