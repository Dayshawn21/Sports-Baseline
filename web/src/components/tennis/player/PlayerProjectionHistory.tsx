import { Select } from 'antd'
import { useSearchParams } from 'react-router-dom'
import ErrorState from '~/components/shared/ErrorState'
import LoadingState from '~/components/shared/LoadingState'
import { ProjectionHistoryChart, type ProjectionHistoryChartPoint } from '~/components/shared/ProjectionHistoryChart'
import { SegmentSwitch } from '~/components/shared/SegmentSwitch'
import { useProjectionHistory } from '~/hooks/useTennisPlayer'
import type { ProjectionHistoryPoint } from '~/types/tennis'
import { formBarLabel } from '~/utils/nflFormWindow'
import {
  filterHistory, historyDefaultStat, historyFilterOptions, historySearch, historyStatOptions, parseHistoryParams, type HistoryFilters,
} from '~/utils/projectionHistory'
import { opponentShortName, MARKET_PARAM } from '~/utils/tennisPlayerProps'
import { marketLabel } from '~/utils/tennisPropBoard'

const ALL = 'all'
const SNAPSHOT_START = '2026-09-25'
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

function shortDate(iso: string | null): string {
  if (!iso) return '--'
  const [, month, day] = iso.split('-').map(Number)
  return `${MONTHS[month - 1]} ${day}`
}

function chartPoint(point: ProjectionHistoryPoint): ProjectionHistoryChartPoint {
  return {
    key: `${point.matchId}-${point.stat}`,
    date: point.matchDate ?? '',
    opponentLabel: opponentShortName(point.opponentName) ?? point.opponentName,
    actual: point.actual,
    line: point.line,
    projection: point.projection,
  }
}

function footnote(version: string, shown: ProjectionHistoryPoint[], unsettled: number): string {
  const first = shortDate(shown[0]?.matchDate ?? null)
  const last = shortDate(shown[shown.length - 1]?.matchDate ?? null)
  const range = !shown.length ? 'no matches' : first === last ? first : `${first} to ${last}`
  const pending = unsettled ? `; ${unsettled} ${unsettled === 1 ? 'line' : 'lines'} across all stats not settled yet` : ''
  return `${version} · ${range} · ${shown.length} ${shown.length === 1 ? 'match' : 'matches'} charted${pending}. Reference only: projections are as frozen before each match, never recomputed.`
}

/** Past matches for one stat: result, line and the props-v3 projection frozen before the match (60a). */
export default function PlayerProjectionHistory({ playerId, playerName }: { playerId: number, playerName: string }) {
  const [params, setParams] = useSearchParams()
  const query = useProjectionHistory(playerId)
  const heading = <h2 className="nfl-player-section-title">Projection history <small>frozen pregame projections against results</small></h2>

  if (query.isLoading) return <section>{heading}<LoadingState message="Loading projection history..." /></section>
  if (query.isError || !query.data) return <section>{heading}<ErrorState error={query.error} onRetry={() => void query.refetch()} /></section>

  const { points, unsettled, projectionVersion } = query.data
  const stats = historyStatOptions(points)
  if (!stats.length) return <section>{heading}<div className="tennis-match-empty">
    No frozen projections have settled for {playerName} yet. Snapshots start {SNAPSHOT_START}.
  </div></section>

  const defaultStat = historyDefaultStat(points, params.get(MARKET_PARAM))
  const filters = parseHistoryParams(params, points, params.get(MARKET_PARAM))
  const options = historyFilterOptions(points, filters.stat)
  const shown = filterHistory(points, filters)
  const update = (next: Partial<HistoryFilters>) => {
    const merged = { ...filters, ...next }
    setParams(previous => new URLSearchParams(historySearch(previous, merged, defaultStat)), { replace: true })
  }

  return <section aria-label={`${playerName} projection history`}>
    {heading}
    <div className="tennis-match-card tennis-player-history">
      <div className="nfl-prop-detail__toolbar">
        <SegmentSwitch label="Stat" value={filters.stat ?? ''} options={stats.map(option => ({ value: option.stat, label: option.label }))}
          onChange={stat => update({ stat, surface: null, opponentId: null })} />
        {options.surfaces.length > 1 && <SegmentSwitch label="Surface" value={filters.surface ?? ALL}
          options={[{ value: ALL, label: 'All' }, ...options.surfaces.map(surface => ({ value: surface, label: surface }))]}
          onChange={surface => update({ surface: surface === ALL ? null : surface })} />}
        {options.opponents.length > 1 && <Select aria-label="Opponent" size="small" style={{ minWidth: 160 }}
          value={filters.opponentId ?? ALL}
          options={[{ value: ALL, label: 'All opponents' }, ...options.opponents.map(o => ({ value: o.id, label: `vs ${o.name}` }))]}
          onChange={(value: number | typeof ALL) => update({ opponentId: value === ALL ? null : value })} />}
      </div>
      <ProjectionHistoryChart points={shown.map(chartPoint)} statLabel={marketLabel(filters.stat ?? '').toLowerCase()}
        dateLabel={point => shortDate(point.date || null)} valueLabel={formBarLabel}
        empty="No matches for this stat under these filters." />
      <p className="tennis-player-history__note">{footnote(projectionVersion, shown, unsettled)}</p>
    </div>
  </section>
}
