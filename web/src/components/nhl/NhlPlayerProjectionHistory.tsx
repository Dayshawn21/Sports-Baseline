import { Select } from 'antd'
import { useSearchParams } from 'react-router-dom'
import { ProjectionHistoryChart, type ProjectionHistoryChartPoint } from '~/components/shared/ProjectionHistoryChart'
import { ProjectionHistorySection, type ProjectionHistoryView } from '~/components/shared/ProjectionHistorySection'
import { SegmentSwitch } from '~/components/shared/SegmentSwitch'
import { useNhlProjectionHistory } from '~/hooks/useNhl'
import type { NhlProjectionHistory, NhlProjectionHistoryPoint } from '~/types/nhl'
import { nhlMarketLabel } from '~/utils/nhlLineOnly'
import {
  filterNhlHistory, nhlHistoryDefaultStat, nhlHistoryFilterOptions, nhlHistorySearch, nhlHistoryStatOptions, nhlHistoryValueLabel,
  parseNhlHistoryParams, type NhlHistoryFilters,
} from '~/utils/nhlProjectionHistory'
import { historyDate, historyFootnote } from '~/utils/projectionHistory'

const ALL = 'all'
const FREEZE_START = '2026-11-05'
const GAME = { one: 'game', many: 'games' }

function chartPoint(point: NhlProjectionHistoryPoint): ProjectionHistoryChartPoint {
  return {
    key: `${point.gameId}-${point.stat}`,
    date: point.gameDate,
    opponentLabel: point.opponentName,
    actual: point.actual,
    line: point.line,
    projection: point.projection,
  }
}

interface Props {
  playerId: number
  playerName: string
  /** The market tab the page has open, the default stat when it has history. */
  openMarket: string | null
}

/** Past games for one stat: result, line and the nhl-reference-v1 projection frozen before puck drop (60b). */
export function NhlPlayerProjectionHistory({ playerId, playerName, openMarket }: Props) {
  const [params, setParams] = useSearchParams()
  const query = useNhlProjectionHistory(playerId)

  const view = ({ points, unsettled, projectionVersion }: NhlProjectionHistory): ProjectionHistoryView => {
    const stats = nhlHistoryStatOptions(points)
    if (!stats.length) return {
      kind: 'empty', className: 'nfl-player-empty',
      message: <>No frozen projections have settled for {playerName} yet. NHL freezing started {FREEZE_START}.</>,
    }
    const defaultStat = nhlHistoryDefaultStat(points, openMarket)
    const filters = parseNhlHistoryParams(params, points, openMarket)
    const options = nhlHistoryFilterOptions(points, filters.stat)
    const shown = filterNhlHistory(points, filters)
    const stat = filters.stat ?? stats[0].stat
    const update = (next: Partial<NhlHistoryFilters>) => {
      const merged = { ...filters, ...next }
      setParams(previous => new URLSearchParams(nhlHistorySearch(previous, merged, defaultStat)), { replace: true })
    }
    return {
      kind: 'chart',
      className: 'nhl-player-history',
      toolbar: <>
        <SegmentSwitch label="Stat" value={stat} options={stats.map(option => ({ value: option.stat, label: option.label }))}
          onChange={value => update({ stat: value, season: null, opponentId: null })} />
        {options.seasons.length > 1 && <SegmentSwitch label="Season" value={filters.season === null ? ALL : String(filters.season)}
          options={[{ value: ALL, label: 'All' }, ...options.seasons.map(option => ({ value: String(option.season), label: option.label }))]}
          onChange={value => update({ season: value === ALL ? null : Number(value) })} />}
        {options.opponents.length > 1 && <Select aria-label="Opponent" size="small" style={{ minWidth: 140 }}
          value={filters.opponentId ?? ALL}
          options={[{ value: ALL, label: 'All opponents' }, ...options.opponents.map(o => ({ value: o.id, label: `vs ${o.name}` }))]}
          onChange={(value: number | typeof ALL) => update({ opponentId: value === ALL ? null : value })} />}
      </>,
      chart: <ProjectionHistoryChart points={shown.map(chartPoint)} statLabel={nhlMarketLabel(stat).toLowerCase()}
        dateLabel={point => historyDate(point.date)} valueLabel={value => nhlHistoryValueLabel(stat, value)}
        empty="No games for this stat under these filters." />,
      noteClassName: 'nhl-player-history__note',
      note: historyFootnote(projectionVersion, shown.map(point => point.gameDate), unsettled, GAME),
    }
  }

  return <ProjectionHistorySection playerName={playerName} query={query}>{view}</ProjectionHistorySection>
}
