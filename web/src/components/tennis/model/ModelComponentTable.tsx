import type { ModelPredictionsResponse, TrackComponentName } from '~/types/tennis'
import { seMultiple, signalClass } from '~/utils/trackRecord'

const COMPONENT_LABELS: Record<TrackComponentName, string> = {
  market: 'Market',
  ensemble: 'Ensemble',
  elo: 'ELO',
  ml: 'LightGBM v6',
}

function signed(value: number): string {
  return `${value >= 0 ? '+' : ''}${value.toFixed(4)}`
}

export default function ModelComponentTable({ data }: { data: ModelPredictionsResponse }) {
  const graded = data.groups.filter((g) => g.n > 0)
  if (graded.length === 0) {
    return <div className="tennis-model-empty">No settled match has both a pre-start prediction and a market price yet.</div>
  }
  return (
    <div className="tennis-model-card tennis-model-pad">
      <div className="tennis-model-scroll">
        <table className="tennis-model-table">
          <thead>
            <tr><th>Source</th><th>Matches</th><th>Log loss</th><th>Brier</th><th>vs market</th></tr>
          </thead>
          {graded.map((group) => (
            <tbody key={group.group}>
              <tr className="is-group"><td colSpan={5}>{group.group}</td></tr>
              {group.components.map((c) => (
                <tr key={c.name} className={c.vsMarket ? '' : 'is-base'}>
                  <td>{COMPONENT_LABELS[c.name]}</td>
                  <td>{group.n}</td>
                  <td>{c.logLoss.toFixed(4)}</td>
                  <td>{c.brier.toFixed(4)}</td>
                  <td className={c.vsMarket ? signalClass(c.vsMarket.signal) || 'is-dim' : ''}>
                    {c.vsMarket ? `${signed(c.vsMarket.mean)} · ${seMultiple(c.vsMarket.mean, c.vsMarket.standardError)}` : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          ))}
        </table>
      </div>
      <p className="tennis-model-note">
        Lower is better. {data.counts.graded.toLocaleString()} settled matches graded
        for {data.modelVersion}, {data.counts.withMarket.toLocaleString()} of them with a market price when the
        prediction was made; each group compares every source on the same matches. A source earns a signal color
        only if it beats the market by more than 2 SE. Challenger is never pooled with ATP and WTA.
      </p>
    </div>
  )
}
