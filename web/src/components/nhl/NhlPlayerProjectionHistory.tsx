import { Select } from 'antd'
import { useSearchParams } from 'react-router-dom'
import ErrorState from '~/components/shared/ErrorState'
import LoadingState from '~/components/shared/LoadingState'
import { ProjectionHistoryChart, type ProjectionHistoryChartPoint } from '~/components/shared/ProjectionHistoryChart'
import { SegmentSwitch } from '~/components/shared/SegmentSwitch'
import { useNhlProjectionHistory } from '~/hooks/useNhl'
import type { NhlProjectionHistoryPoint } from '~/types/nhl'
import { nhlMarketLabel } from '~/utils/nhlLineOnly'
import {
  filterNhlHistory, nhlHistoryDefaultStat, nhlHistoryFilterOptions, nhlHistorySearch, nhlHistoryStatOptions, nhlHistoryValueLabel,
  parseNhlHistoryParams, type NhlHistoryFilters,
} from '~/utils/nhlProjectionHistory'

const ALL = 'all'
const FREEZE_START = '2026-11-05'
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

function shortDate(iso: string | undefined): string {
  if (!iso) return '--'
  const [, month, day] = iso.split('-').map(Number)
  return `${MONTHS[month - 1]} ${day}`
}

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

function footnote(version: string, shown: NhlProjectionHistoryPoint[], unsettled: number): string {
  const first = shortDate(shown[0]?.gameDate)
  const last = shortDate(shown[shown.length - 1]?.gameDate)
  const range = !shown.length ? 'no games' : first === last ? first : `${first} to ${last}`
  const pending = unsettled ? `; ${unsettled} ${unsettled === 1 ? 'line' : 'lines'} across all stats not settled yet` : ''
  return `${version} · ${range} · ${shown.length} ${shown.length === 1 ? 'game' : 'games'} charted${pending}. Reference only: projections are as frozen before each game, never recomputed.`
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
  const heading = <h2 className="nfl-player-section-title">Projection history <small>frozen pregame projections against results</small></h2>

  if (query.isLoading) return <section>{heading}<LoadingState message="Loading projection history..." /></section>
  if (query.isError || !query.data) return <section>{heading}<ErrorState error={query.error} onRetry={() => void query.refetch()} /></section>

  const { points, unsettled, projectionVersion } = query.data
  const stats = nhlHistoryStatOptions(points)
  if (!stats.length) return <section>{heading}<div className="nfl-player-empty">
    No frozen projections have settled for {playerName} yet. NHL freezing started {FREEZE_START}.
  </div></section>

  const defaultStat = nhlHistoryDefaultStat(points, openMarket)
  const filters = parseNhlHistoryParams(params, points, openMarket)
  const options = nhlHistoryFilterOptions(points, filters.stat)
  const shown = filterNhlHistory(points, filters)
  const stat = filters.stat ?? stats[0].stat
  const update = (next: Partial<NhlHistoryFilters>) => {
    const merged = { ...filters, ...next }
    setParams(previous => new URLSearchParams(nhlHistorySearch(previous, merged, defaultStat)), { replace: true })
  }

  return <section aria-label={`${playerName} projection history`}>
    {heading}
    <div className="nhl-player-history">
      <div className="nfl-prop-detail__toolbar">
        <SegmentSwitch label="Stat" value={stat} options={stats.map(option => ({ value: option.stat, label: option.label }))}
          onChange={value => update({ stat: value, season: null, opponentId: null })} />
        {options.seasons.length > 1 && <SegmentSwitch label="Season" value={filters.season === null ? ALL : String(filters.season)}
          options={[{ value: ALL, label: 'All' }, ...options.seasons.map(option => ({ value: String(option.season), label: option.label }))]}
          onChange={value => update({ season: value === ALL ? null : Number(value) })} />}
        {options.opponents.length > 1 && <Select aria-label="Opponent" size="small" style={{ minWidth: 140 }}
          value={filters.opponentId ?? ALL}
          options={[{ value: ALL, label: 'All opponents' }, ...options.opponents.map(o => ({ value: o.id, label: `vs ${o.name}` }))]}
          onChange={(value: number | typeof ALL) => update({ opponentId: value === ALL ? null : value })} />}
      </div>
      <ProjectionHistoryChart points={shown.map(chartPoint)} statLabel={nhlMarketLabel(stat).toLowerCase()}
        dateLabel={point => shortDate(point.date)} valueLabel={value => nhlHistoryValueLabel(stat, value)}
        empty="No games for this stat under these filters." />
      <p className="nhl-player-history__note">{footnote(projectionVersion, shown, unsettled)}</p>
    </div>
  </section>
}
