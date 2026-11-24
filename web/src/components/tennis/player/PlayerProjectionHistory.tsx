import { Select } from 'antd'
import { useSearchParams } from 'react-router-dom'
import { ProjectionHistoryChart, type ProjectionHistoryChartPoint } from '~/components/shared/ProjectionHistoryChart'
import { ProjectionHistorySection, type ProjectionHistoryView } from '~/components/shared/ProjectionHistorySection'
import { SegmentSwitch } from '~/components/shared/SegmentSwitch'
import { useProjectionHistory } from '~/hooks/useTennisPlayer'
import type { ProjectionHistory, ProjectionHistoryPoint } from '~/types/tennis'
import { formBarLabel } from '~/utils/nflFormWindow'
import {
  filterHistory, historyDate, historyDefaultStat, historyFilterOptions, historyFootnote, historySearch, historyStatOptions, parseHistoryParams,
  type HistoryFilters,
} from '~/utils/projectionHistory'
import { opponentShortName, MARKET_PARAM } from '~/utils/tennisPlayerProps'
import { marketLabel } from '~/utils/tennisPropBoard'

const ALL = 'all'
const SNAPSHOT_START = '2026-09-25'
const MATCH = { one: 'match', many: 'matches' }

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

/** Past matches for one stat: result, line and the props-v3 projection frozen before the match (60a). */
export default function PlayerProjectionHistory({ playerId, playerName }: { playerId: number, playerName: string }) {
  const [params, setParams] = useSearchParams()
  const query = useProjectionHistory(playerId)

  const view = ({ points, unsettled, projectionVersion }: ProjectionHistory): ProjectionHistoryView => {
    const stats = historyStatOptions(points)
    if (!stats.length) return {
      kind: 'empty', className: 'tennis-match-empty',
      message: <>No frozen projections have settled for {playerName} yet. Snapshots start {SNAPSHOT_START}.</>,
    }
    const defaultStat = historyDefaultStat(points, params.get(MARKET_PARAM))
    const filters = parseHistoryParams(params, points, params.get(MARKET_PARAM))
    const options = historyFilterOptions(points, filters.stat)
    const shown = filterHistory(points, filters)
    const update = (next: Partial<HistoryFilters>) => {
      const merged = { ...filters, ...next }
      setParams(previous => new URLSearchParams(historySearch(previous, merged, defaultStat)), { replace: true })
    }
    return {
      kind: 'chart',
      className: 'tennis-match-card tennis-player-history',
      toolbar: <>
        <SegmentSwitch label="Stat" value={filters.stat ?? ''} options={stats.map(option => ({ value: option.stat, label: option.label }))}
          onChange={stat => update({ stat, surface: null, opponentId: null })} />
        {options.surfaces.length > 1 && <SegmentSwitch label="Surface" value={filters.surface ?? ALL}
          options={[{ value: ALL, label: 'All' }, ...options.surfaces.map(surface => ({ value: surface, label: surface }))]}
          onChange={surface => update({ surface: surface === ALL ? null : surface })} />}
        {options.opponents.length > 1 && <Select aria-label="Opponent" size="small" style={{ minWidth: 160 }}
          value={filters.opponentId ?? ALL}
          options={[{ value: ALL, label: 'All opponents' }, ...options.opponents.map(o => ({ value: o.id, label: `vs ${o.name}` }))]}
          onChange={(value: number | typeof ALL) => update({ opponentId: value === ALL ? null : value })} />}
      </>,
      chart: <ProjectionHistoryChart points={shown.map(chartPoint)} statLabel={marketLabel(filters.stat ?? '').toLowerCase()}
        dateLabel={point => historyDate(point.date || null)} valueLabel={formBarLabel}
        empty="No matches for this stat under these filters." />,
      noteClassName: 'tennis-player-history__note',
      note: historyFootnote(projectionVersion, shown.map(point => point.matchDate), unsettled, MATCH),
    }
  }

  return <ProjectionHistorySection playerName={playerName} query={query}>{view}</ProjectionHistorySection>
}
