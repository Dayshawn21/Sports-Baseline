import type { NflModelFit, NflModelPropLines } from '~/types/nfl'
import { MARKET_LABELS } from '~/utils/nflLabels'

// Everything in this section is display-only calibration, so nothing here is ever colored.
const pct = (value: number | null) => (value === null ? '—' : `${(value * 100).toFixed(1)}%`)
const signed4 = (value: number) => `${value > 0 ? '+' : ''}${value.toFixed(4)}`

export function NflOverProbabilityFit({ data }: { data: NflModelFit }) {
  const { rule } = data
  return (
    <section className="nfl-model-card">
      <div className="nfl-model-card__head">
        <span className="nfl-model-label">Fit on the {data.fitSeason} replay</span>
        <span className="nfl-model-muted">cross-fitted by week parity · {data.projectionVersion}</span>
      </div>
      <div className="nfl-model-card__body">
        {!data.served && (
          <p className="nfl-model-rule">
            <b>Not served.</b> The projection model has changed since this fit, so the slate hides P(over) until the fit
            is regenerated.
          </p>
        )}
        <div className="nfl-model-scroll">
          <table className="nfl-model-table">
            <thead>
              <tr>
                <th className="text">Market</th><th className="text">Status</th><th>Cases</th><th>ECE</th>
                <th>Worst gap</th><th>Brier vs normal</th><th>Over at projection</th>
              </tr>
            </thead>
            <tbody>
              {data.markets.map((m) => (
                <tr key={m.market} className={m.verdict === 'hide' ? 'is-hidden' : undefined}>
                  <td className="text">{MARKET_LABELS[m.market] ?? m.market}</td>
                  <td className="text">{m.verdict === 'show' ? 'Shown' : 'Hidden'}</td>
                  <td>{m.cases.toLocaleString()}</td>
                  <td>{m.ece.toFixed(3)}</td>
                  <td>{m.worstGap === null ? '—' : m.worstGap.toFixed(3)}</td>
                  <td>{signed4(m.brier - m.normalBrier)}</td>
                  <td>{pct(m.atProjectionPredicted)} / {pct(m.atProjectionObserved)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="nfl-model-note">
          A market shows only with {rule.minCases}+ cases, ECE &le; {rule.maxEce}, no bin of {rule.minBinPairs}+ pairs off
          by more than {rule.maxBinGap}, and Brier no worse than a normal (a negative Brier difference beats it). Over at
          projection is predicted / observed at the line nearest the projection: in every market a line set at the
          projection goes over less than half the time. Shown means displayed muted; it is never ranked until 27h.
        </p>
      </div>
    </section>
  )
}

export function NflOverProbabilityForward({ data }: { data: NflModelPropLines }) {
  if (data.overProbability.length === 0) {
    return <div className="model-section-empty">No settled line has a served P(over) yet this season.</div>
  }
  return (
    <section className="nfl-model-card">
      <div className="nfl-model-card__head">
        <span className="nfl-model-label">Served P(over) on {data.season} lines</span>
        <span className="nfl-model-muted">forward read · settled over or under</span>
      </div>
      <div className="nfl-model-card__body">
        <div className="nfl-model-scroll">
          <table className="nfl-model-table">
            <thead>
              <tr>
                <th className="text">Odds type</th><th>Scored</th><th>No P(over)</th><th>Predicted</th><th>Went over</th>
                <th>Brier</th>
              </tr>
            </thead>
            <tbody>
              {data.overProbability.map((row) => (
                <tr key={row.oddsType} className={row.oddsType === 'all' ? 'is-total' : undefined}>
                  <td className="text">{row.oddsType === 'all' ? 'All' : row.oddsType[0].toUpperCase() + row.oddsType.slice(1)}</td>
                  <td>{row.scored.toLocaleString()}</td>
                  <td>{row.unscored.toLocaleString()}</td>
                  <td>{pct(row.meanPredicted)}</td>
                  <td>{pct(row.overRate)}</td>
                  <td>{row.brier === null ? '—' : row.brier.toFixed(4)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {data.reliability.length > 0 && (
          <div className="nfl-model-rates">
            <div className="nfl-model-muted">Reliability, all scored lines</div>
            {data.reliability.map((bin) => (
              <div key={bin.meanPredicted} className="nfl-model-rate is-plain">
                <span>{bin.n.toLocaleString()} lines</span>
                <b>predicted {pct(bin.meanPredicted)} · went over {pct(bin.observed)}</b>
              </div>
            ))}
          </div>
        )}
        <p className="nfl-model-note">
          Every settled line counts here, so a player&apos;s goblin and demon ladder counts several times; that is why this
          read carries no error bar or color. It checks whether the 2025 fit still describes 2026 lines.
        </p>
      </div>
    </section>
  )
}
