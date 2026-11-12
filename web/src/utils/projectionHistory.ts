import type { ProjectionHistoryPoint } from '~/types/tennis'
import { playerSearch } from '~/utils/nflPlayer'
import { marketKey, marketTitle } from '~/utils/tennisPropBoard'

export const HISTORY_STAT_PARAM = 'hstat'
export const HISTORY_SURFACE_PARAM = 'hsurface'
export const HISTORY_OPPONENT_PARAM = 'hopp'

export interface HistoryStatOption {
  stat: string
  label: string
  count: number
}

export interface HistoryOpponentOption {
  id: number
  name: string
  count: number
}

export interface HistoryFilterOptions {
  surfaces: string[]
  opponents: HistoryOpponentOption[]
}

export interface HistoryFilters {
  stat: string | null
  surface: string | null
  opponentId: number | null
}

/** What the chart needs from any sport's point. */
export interface ScalePoint {
  actual: number
  line: number
  projection: number | null
}

export interface HistoryColumn<T extends ScalePoint> {
  point: T
  actualPct: number
  linePct: number
  projectionPct: number | null
  vsLine: 'above' | 'below' | 'push'
}

function surfaceKey(surface: string | null): string | null {
  const value = surface?.trim().toLowerCase()
  return value ? value : null
}

/** Stats with a settled point, keyed as the `?market=` tabs are, most charted first. */
export function historyStatOptions(points: readonly ProjectionHistoryPoint[]): HistoryStatOption[] {
  const counts = new Map<string, number>()
  for (const point of points) counts.set(marketKey(point.stat), (counts.get(marketKey(point.stat)) ?? 0) + 1)
  return [...counts]
    .map(([stat, count]) => ({ stat, label: marketTitle(stat), count }))
    .sort((a, b) => b.count - a.count || a.label.localeCompare(b.label))
}

function statPoints(points: readonly ProjectionHistoryPoint[], stat: string | null): ProjectionHistoryPoint[] {
  return stat === null ? [] : points.filter(point => marketKey(point.stat) === stat)
}

/** The surfaces and opponents a stat has points for; opponents faced most often first. */
export function historyFilterOptions(points: readonly ProjectionHistoryPoint[], stat: string | null): HistoryFilterOptions {
  const surfaces = new Map<string, string>()
  const opponents = new Map<number, HistoryOpponentOption>()
  for (const point of statPoints(points, stat)) {
    const key = surfaceKey(point.surface)
    if (key && !surfaces.has(key)) surfaces.set(key, point.surface!.trim())
    const seen = opponents.get(point.opponentId)
    opponents.set(point.opponentId, { id: point.opponentId, name: point.opponentName, count: (seen?.count ?? 0) + 1 })
  }
  return {
    surfaces: [...surfaces.values()].sort((a, b) => a.localeCompare(b)),
    opponents: [...opponents.values()].sort((a, b) => b.count - a.count || a.name.localeCompare(b.name)),
  }
}

/** One stat's points under the surface and opponent filters, oldest match first. */
export function filterHistory(points: readonly ProjectionHistoryPoint[], filters: HistoryFilters): ProjectionHistoryPoint[] {
  const surface = surfaceKey(filters.surface)
  return statPoints(points, filters.stat)
    .filter(point => surface === null || surfaceKey(point.surface) === surface)
    .filter(point => filters.opponentId === null || point.opponentId === filters.opponentId)
    .sort((a, b) => (a.matchDate ?? '').localeCompare(b.matchDate ?? '') || a.matchId - b.matchId)
}

function percent(value: number, max: number): number {
  return max > 0 ? Math.max(0, value) / max * 100 : 0
}

/** Result, line and projection on one shared scale, so the three marks can be compared directly. */
export function historyScale<T extends ScalePoint>(points: readonly T[]): Array<HistoryColumn<T>> {
  const max = Math.max(0, ...points.flatMap(point => [point.actual, point.line, point.projection ?? 0]))
  return points.map(point => ({
    point,
    actualPct: percent(point.actual, max),
    linePct: percent(point.line, max),
    projectionPct: point.projection === null ? null : percent(point.projection, max),
    vsLine: point.actual > point.line ? 'above' : point.actual < point.line ? 'below' : 'push',
  }))
}

function knownStat(points: readonly ProjectionHistoryPoint[], value: string | null): string | null {
  if (value === null) return null
  return historyStatOptions(points).some(option => option.stat === marketKey(value)) ? marketKey(value) : null
}

/** The stat shown with no `?hstat=`: the open market tab when it has history, else the most charted. */
export function historyDefaultStat(points: readonly ProjectionHistoryPoint[], preferredStat: string | null = null): string | null {
  return knownStat(points, preferredStat) ?? historyStatOptions(points)[0]?.stat ?? null
}

/**
 * The filters in the URL, kept only while they still match: an unknown stat falls back to
 * the preferred stat (the open market tab) or the first option, and a surface or opponent
 * that stat has no point for is dropped.
 */
export function parseHistoryParams(
  params: URLSearchParams, points: readonly ProjectionHistoryPoint[], preferredStat: string | null = null,
): HistoryFilters {
  const stat = knownStat(points, params.get(HISTORY_STAT_PARAM)) ?? historyDefaultStat(points, preferredStat)
  const options = historyFilterOptions(points, stat)
  const surface = surfaceKey(params.get(HISTORY_SURFACE_PARAM))
  const opponentParam = params.get(HISTORY_OPPONENT_PARAM)
  const opponentId = opponentParam === null ? Number.NaN : Number(opponentParam)
  return {
    stat,
    surface: options.surfaces.find(option => surfaceKey(option) === surface) ?? null,
    opponentId: options.opponents.some(option => option.id === opponentId) ? opponentId : null,
  }
}

/** Writes the filters, leaving every other param alone; the default stat drops `?hstat=`. */
export function historySearch(params: URLSearchParams, filters: HistoryFilters, defaultStat: string | null): string {
  return playerSearch(params, {
    [HISTORY_STAT_PARAM]: filters.stat === null || filters.stat === defaultStat ? null : filters.stat,
    [HISTORY_SURFACE_PARAM]: surfaceKey(filters.surface),
    [HISTORY_OPPONENT_PARAM]: filters.opponentId === null ? null : String(filters.opponentId),
  })
}
