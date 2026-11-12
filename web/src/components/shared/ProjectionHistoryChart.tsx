import type { CSSProperties } from 'react'
import { historyScale } from '~/utils/projectionHistory'
import './projection-history.css'

export interface ProjectionHistoryChartPoint {
  key: string
  date: string
  opponentLabel: string
  actual: number
  line: number
  projection: number | null
}

interface Props {
  points: ProjectionHistoryChartPoint[]
  /** Short date under each column ("Oct 2"). */
  dateLabel: (point: ProjectionHistoryChartPoint) => string
  valueLabel: (value: number) => string
  /** The stat's name in each column's accessible label ("aces"). */
  statLabel: string
  empty: string
}

function columnLabel(point: ProjectionHistoryChartPoint, props: Props): string {
  const projected = point.projection === null ? 'no projection' : `projected ${props.valueLabel(point.projection)}`
  return `${props.dateLabel(point)} vs ${point.opponentLabel}: ${props.valueLabel(point.actual)} ${props.statLabel}, line ${props.valueLabel(point.line)}, ${projected}`
}

/** Past games oldest to newest: the bar is the result, the tick that game's line, the ring the projection frozen before it. Grayscale only. */
export function ProjectionHistoryChart(props: Props) {
  const { points, dateLabel, valueLabel, empty } = props
  if (!points.length) return <p className="projection-history__empty">{empty}</p>
  const columns = historyScale(points)
  return <div className="projection-history">
    <p className="projection-history__legend" aria-hidden="true">
      <span><i className="projection-history__key is-bar" />Result</span>
      <span><i className="projection-history__key is-tick" />Line</span>
      <span><i className="projection-history__key is-ring" />Frozen projection</span>
    </p>
    <div className="projection-history__scroll">
      <ol className="projection-history__grid" style={{ '--cols': columns.length } as CSSProperties}>
        {columns.map(({ point, actualPct, linePct, projectionPct, vsLine }) => <li key={point.key} className={`projection-history__col is-${vsLine}`} aria-label={columnLabel(point, props)}>
          <div className="projection-history__plot" aria-hidden="true"
            style={{ '--h': `${actualPct}%`, '--line': `${linePct}%`, ...(projectionPct === null ? {} : { '--proj': `${projectionPct}%` }) } as CSSProperties}>
            <span className="projection-history__val">{valueLabel(point.actual)}</span>
            <span className="projection-history__bar" />
            <span className="projection-history__tick" />
            {projectionPct !== null && <span className="projection-history__ring" />}
          </div>
          <span className="projection-history__opp" aria-hidden="true">{point.opponentLabel}<small>{dateLabel(point)}</small></span>
        </li>)}
      </ol>
    </div>
  </div>
}
