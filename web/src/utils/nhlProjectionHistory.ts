import type { NhlLineOnlyMarket, NhlProjectionHistoryPoint } from '~/types/nhl'
import { playerSearch } from '~/utils/nflPlayer'
import { NHL_LINE_ONLY_MARKETS, nhlMarketLabel } from '~/utils/nhlLineOnly'
import { nhlLogValue } from '~/utils/nhlPlayer'
import { HISTORY_OPPONENT_PARAM, HISTORY_STAT_PARAM, type HistoryOpponentOption } from '~/utils/projectionHistory'

export const HISTORY_SEASON_PARAM = 'hseason'

export interface NhlHistoryStatOption {
  stat: NhlLineOnlyMarket
  label: string
  count: number
}

export interface NhlHistorySeasonOption {
  season: number
  label: string
}

export interface NhlHistoryFilterOptions {
  seasons: NhlHistorySeasonOption[]
  opponents: HistoryOpponentOption[]
}

export interface NhlHistoryFilters {
  stat: NhlLineOnlyMarket | null
  season: number | null
  opponentId: number | null
}

function isMarket(value: string | null): value is NhlLineOnlyMarket {
  return value !== null && (NHL_LINE_ONLY_MARKETS as readonly string[]).includes(value)
}

/** "2026-27": NHL seasons are named by the year they start in. */
export function nhlSeasonLabel(season: number): string {
  return `${season}-${String((season + 1) % 100).padStart(2, '0')}`
}

/**
 * A chart value: time on ice keeps two decimals, since lines move in quarter minutes and a
 * one-decimal label would show a 21.75 line and a 21.79 projection as the same number.
 */
export function nhlHistoryValueLabel(stat: NhlLineOnlyMarket, value: number): string {
  return stat === 'time_on_ice' ? String(Number(value.toFixed(2))) : nhlLogValue(stat, value)
}

/** Markets with a settled point, keyed as the `?market=` tabs are, most charted first. */
export function nhlHistoryStatOptions(points: readonly NhlProjectionHistoryPoint[]): NhlHistoryStatOption[] {
  const counts = new Map<NhlLineOnlyMarket, number>()
  for (const point of points) counts.set(point.stat, (counts.get(point.stat) ?? 0) + 1)
  return [...counts]
    .map(([stat, count]) => ({ stat, label: nhlMarketLabel(stat), count }))
    .sort((a, b) => b.count - a.count || a.label.localeCompare(b.label))
}

function statPoints(points: readonly NhlProjectionHistoryPoint[], stat: NhlLineOnlyMarket | null): NhlProjectionHistoryPoint[] {
  return stat === null ? [] : points.filter(point => point.stat === stat)
}

/** The seasons (newest first) and opposing teams (most faced first) a stat has points for. */
export function nhlHistoryFilterOptions(
  points: readonly NhlProjectionHistoryPoint[], stat: NhlLineOnlyMarket | null,
): NhlHistoryFilterOptions {
  const seasons = new Set<number>()
  const opponents = new Map<number, HistoryOpponentOption>()
  for (const point of statPoints(points, stat)) {
    seasons.add(point.season)
    const seen = opponents.get(point.opponentId)
    opponents.set(point.opponentId, { id: point.opponentId, name: point.opponentName, count: (seen?.count ?? 0) + 1 })
  }
  return {
    seasons: [...seasons].sort((a, b) => b - a).map(season => ({ season, label: nhlSeasonLabel(season) })),
    opponents: [...opponents.values()].sort((a, b) => b.count - a.count || a.name.localeCompare(b.name)),
  }
}

/** One stat's points under the season and opponent filters, oldest game first. */
export function filterNhlHistory(points: readonly NhlProjectionHistoryPoint[], filters: NhlHistoryFilters): NhlProjectionHistoryPoint[] {
  return statPoints(points, filters.stat)
    .filter(point => filters.season === null || point.season === filters.season)
    .filter(point => filters.opponentId === null || point.opponentId === filters.opponentId)
    .sort((a, b) => a.gameDate.localeCompare(b.gameDate) || a.gameId - b.gameId)
}

function knownStat(points: readonly NhlProjectionHistoryPoint[], value: string | null): NhlLineOnlyMarket | null {
  return isMarket(value) && points.some(point => point.stat === value) ? value : null
}

/** The stat shown with no `?hstat=`: the open market tab when it has history, else the most charted. */
export function nhlHistoryDefaultStat(
  points: readonly NhlProjectionHistoryPoint[], preferredStat: string | null = null,
): NhlLineOnlyMarket | null {
  return knownStat(points, preferredStat) ?? nhlHistoryStatOptions(points)[0]?.stat ?? null
}

function numberParam(params: URLSearchParams, name: string): number {
  const value = params.get(name)
  return value === null ? Number.NaN : Number(value)
}

/** The filters in the URL, kept only while they still match the chosen stat's points. */
export function parseNhlHistoryParams(
  params: URLSearchParams, points: readonly NhlProjectionHistoryPoint[], preferredStat: string | null = null,
): NhlHistoryFilters {
  const stat = knownStat(points, params.get(HISTORY_STAT_PARAM)) ?? nhlHistoryDefaultStat(points, preferredStat)
  const options = nhlHistoryFilterOptions(points, stat)
  const season = numberParam(params, HISTORY_SEASON_PARAM)
  const opponentId = numberParam(params, HISTORY_OPPONENT_PARAM)
  return {
    stat,
    season: options.seasons.some(option => option.season === season) ? season : null,
    opponentId: options.opponents.some(option => option.id === opponentId) ? opponentId : null,
  }
}

/** Writes the filters, leaving every other param (`date`, `market`) alone; the default stat drops `?hstat=`. */
export function nhlHistorySearch(params: URLSearchParams, filters: NhlHistoryFilters, defaultStat: NhlLineOnlyMarket | null): string {
  return playerSearch(params, {
    [HISTORY_STAT_PARAM]: filters.stat === null || filters.stat === defaultStat ? null : filters.stat,
    [HISTORY_SEASON_PARAM]: filters.season === null ? null : String(filters.season),
    [HISTORY_OPPONENT_PARAM]: filters.opponentId === null ? null : String(filters.opponentId),
  })
}
