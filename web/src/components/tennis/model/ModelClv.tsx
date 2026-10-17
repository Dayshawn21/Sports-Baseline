import type { ModelPredictionsResponse, TrackClvLine } from '~/types/tennis'

const pct = (part: number, whole: number) => (whole ? `${((part / whole) * 100).toFixed(1)}%` : '—')
const points = (value: number) => `${value >= 0 ? '+' : ''}${(value * 100).toFixed(2)}`

function GroupLine({ line }: { line: TrackClvLine }) {
  return (
    <tr>
      <td>{line.group === 'all' ? 'All' : line.group}{line.minGap > 0 && `, gap ≥ ${Math.round(line.minGap * 100)} pts`}</td>
      <td>{line.eligible.toLocaleString()}</td>
      <td>{line.moved.toLocaleString()}</td>
      <td>{pct(line.toward, line.moved)}</td>
      <td>{points(line.meanMoveToward)}</td>
    </tr>
  )
}

export default function ModelClv({ data }: { data: ModelPredictionsResponse }) {
  const all = data.clv.find((c) => c.group === 'all' && c.minGap === 0)
  if (!all || all.eligible === 0) {
    return <div className="tennis-model-empty">No graded match has a market price at prediction time and a closing price yet.</div>
  }
  const towardShare = all.moved ? all.toward / all.moved : 0
  return (
    <div className="tennis-model-card tennis-model-pad">
      <div className="tennis-model-clv">
        <div>
          <div className="tennis-model-verdict__label">Moved prices</div>
          <div className="tennis-model-clv__value">{all.moved.toLocaleString()}</div>
          <div className="tennis-model-clv__sub">of {all.eligible.toLocaleString()} with a price at prediction and at the close</div>
        </div>
        <div>
          <div className="tennis-model-verdict__label">Toward the ensemble</div>
          <div className="tennis-model-clv__value">{pct(all.toward, all.moved)}</div>
          <div className="tennis-model-clv__sub">{all.toward.toLocaleString()} toward · {all.away.toLocaleString()} away</div>
        </div>
        <div>
          <div className="tennis-model-verdict__label">Mean move</div>
          <div className="tennis-model-clv__value">{points(all.meanMoveToward)}</div>
          <div className="tennis-model-clv__sub">implied-probability points toward the model, unmoved prices counted as 0</div>
        </div>
      </div>
      {all.moved > 0 && (
        <>
          <div className="tennis-model-split" aria-hidden="true">
            <i className="is-toward" style={{ width: `${towardShare * 100}%` }} />
            <i className="is-away" style={{ width: `${(1 - towardShare) * 100}%` }} />
          </div>
          <div className="tennis-model-split-labels"><span>Toward {pct(all.toward, all.moved)}</span><span>Away {pct(all.away, all.moved)}</span></div>
        </>
      )}
      <div className="tennis-model-scroll">
        <table className="tennis-model-table tennis-model-clv-table">
          <thead><tr><th>Group</th><th>Priced</th><th>Moved</th><th>Toward</th><th>Mean move</th></tr></thead>
          <tbody>{data.clv.map((line) => <GroupLine key={`${line.group}-${line.minGap}`} line={line} />)}</tbody>
        </table>
      </div>
      <p className="tennis-model-note">
        The same book&apos;s last moneyline before the start, against its price when the prediction was made. Gray
        throughout: CLV has no pre-registered rule on this page, so it never takes a signal color.
      </p>
    </div>
  )
}
