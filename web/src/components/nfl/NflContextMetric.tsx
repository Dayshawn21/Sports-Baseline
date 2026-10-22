import type { NflContextMetric as Metric } from '~/types/nfl'
import { contextCoverage, contextDates, contextUnavailable, contextValue } from '~/utils/nflMatchupContext'

export function NflContextMetric({ metric, share = false }: { metric: Metric, share?: boolean }) {
  const dates = contextDates(metric)
  const unavailable = contextUnavailable(metric)
  return <div className="nfl-context-metric">
    <span className="nfl-context-metric__value">{contextValue(metric, share)}</span>
    <small>{contextCoverage(metric)}</small>
    {dates && <small>{dates}</small>}
    {unavailable && <small>{unavailable}</small>}
  </div>
}
