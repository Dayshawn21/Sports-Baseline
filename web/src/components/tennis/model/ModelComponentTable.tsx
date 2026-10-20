import type { ModelPredictionsResponse, TrackComponentName } from '~/types/tennis'
import { pairedLossText, seMultiple, signalClass } from '~/utils/trackRecord'

const COMPONENT_LABELS: Record<TrackComponentName, string> = {
  market: 'Market',
  ensemble: 'Ensemble',
  elo: 'ELO',
  ml: 'LightGBM v6',
}

function signed(value: number): string {
  return `${value >= 0 ? '+' : ''}${value.toFixed(4)}`
}

interface Props {
  data: ModelPredictionsResponse
  sample?: 'all-four' | 'ensemble-market'
}

export default function ModelComponentTable({ data, sample = 'all-four' }: Props) {
  const paired = sample === 'ensemble-market'
  const graded = (paired ? data.ensembleMarketGroups : data.groups).filter((g) => g.n > 0)
  const title = paired ? 'Ensemble versus market' : 'All four components'
  return (
    <div className="tennis-model-card tennis-model-pad">
      <h3 className="tennis-model-subhead">{title}</h3>
      <p className="tennis-model-note">
        {paired
          ? 'Requires ensemble and market probabilities only; ELO and ML may be absent. Market-free fallback rows are excluded, so this comparison does not validate that fallback.'
          : 'Requires ensemble, market, ELO and ML probabilities on every row. These sample counts also apply to the ELO and ML comparisons.'}
      </p>
      {graded.length === 0
        ? <div className="tennis-model-empty">{paired
          ? 'No settled match has both stored ensemble and market probabilities for this version yet.'
          : 'No settled match has all four probabilities for this version yet.'}</div>
        : <div className="tennis-model-scroll">
        <table className="tennis-model-table" aria-label={title}>
          <thead>
            <tr><th>Source</th><th>Matches</th><th>Log loss</th><th>Brier</th><th>{paired ? 'vs market (1 SE)' : 'vs market'}</th></tr>
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
                    {c.vsMarket ? paired ? pairedLossText(c.vsMarket) : `${signed(c.vsMarket.mean)} · ${seMultiple(c.vsMarket.mean, c.vsMarket.standardError)}` : '-'}
                  </td>
                </tr>
              ))}
            </tbody>
          ))}
        </table>
      </div>}
      <p className="tennis-model-note">
        Lower is better. {data.counts.graded.toLocaleString()} settled matches graded
        for {data.modelVersion}, {data.counts.withMarket.toLocaleString()} of them with a market price when the
        prediction was made; each group compares every source on the same matches. A source earns a signal color
        only if it beats the market by more than 2 SE. Challenger is never pooled with ATP and WTA.
        {paired && ' The difference is ensemble minus market log loss, with one standard error; negative favors the ensemble.'}
      </p>
    </div>
  )
}
