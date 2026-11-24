import { GameLogBars } from '~/components/nfl/NflPropDetailSections'
import { useTennisPropReasons } from '~/hooks/useTennisPropReasons'
import type { PropReason } from '~/types/tennis'
import { reasonsChartSample } from '~/utils/tennisPropReasons'
import './tennis-prop-reasons.css'

const TENNIS_SEASON_START_MONTH = 0

function ReasonList({ title, items }: { title: string, items: PropReason[] }) {
  return <section className="tennis-prop-reasons__side" aria-label={title}>
    <h4>{title}</h4>
    {items.length ? <ul>{items.map(item => <li key={item.key}>{item.text}</li>)}</ul>
      : <p className="tennis-prop-reasons__empty">Nothing in the recent data points this way.</p>}
  </section>
}

/** Why a PrizePicks line could go over or under (63). Gray reference on every row, adopted or not. */
export function TennisPropReasons({ propId }: { propId: number }) {
  const reasons = useTennisPropReasons(propId, true)
  if (reasons.isLoading) return <p className="tennis-prop-reasons__status" role="status">Loading reasons...</p>
  if (reasons.isError || !reasons.data) {
    return <p className="tennis-prop-reasons__status" role="status">
      Reasons are unavailable right now.{' '}
      <button type="button" className="tennis-prop-text-action" onClick={() => void reasons.refetch()}>Try again</button>
    </p>
  }
  const data = reasons.data
  const sample = reasonsChartSample(data.recent, data.line)
  return <div className="tennis-prop-reasons">
    <div className="tennis-prop-reasons__chart">
      <h4>{data.recent.length ? `Last ${data.recent.length} completed matches · line ${data.line}` : 'Recent matches'}</h4>
      {data.recent.length ? <GameLogBars row={{ market: data.statType, line: data.line, segment: 'full_game' }} sample={sample} seasonStartMonth={TENNIS_SEASON_START_MONTH} />
        : <p className="tennis-prop-reasons__empty">No recent results to chart.</p>}
    </div>
    <ReasonList title="Why it could go over" items={data.over} />
    <ReasonList title="Why it could go under" items={data.under} />
    <footer className="tennis-prop-reasons__foot">
      {data.caveats.length > 0 && <ul className="tennis-prop-reasons__caveats" aria-label="Caveats">
        {data.caveats.map(item => <li key={item.key}>{item.text}</li>)}
      </ul>}
      <p>Reference, not a pick. Built from the model projection and the player's recent completed matches.</p>
    </footer>
  </div>
}
