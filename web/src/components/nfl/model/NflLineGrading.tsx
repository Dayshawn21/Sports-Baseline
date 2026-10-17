import type { CSSProperties } from 'react'
import type { NflHitRow, NflModelPropLines } from '~/types/nfl'
import { MARKET_LABELS } from '~/utils/nflLabels'
import { signalClass } from '~/utils/trackRecord'

const pct = (value: number) => `${(value * 100).toFixed(1)}%`

function RateRow({ label, row, breakEven }: { label: string, row: NflHitRow, breakEven: number }) {
  const tone = signalClass(row.signal)
  const meter = { '--v': `${(row.hitRate ?? 0) * 100}%`, '--be': `${breakEven * 100}%` } as CSSProperties
  return (
    <div className="nfl-model-rate">
      <span>{label}</span>
      <span className="nfl-model-meter" style={meter} aria-hidden="true"><i className={tone} /><b /></span>
      <b className={tone}>
        {row.hitRate === null ? '—' : pct(row.hitRate)} <small>n {row.calls.toLocaleString()}</small>
      </b>
    </div>
  )
}

export default function NflLineGrading({ data }: { data: NflModelPropLines }) {
  const { calls, breakEven, coverage } = data
  if (calls.calls === 0) {
    return <div className="model-section-empty">No standard line has a settled model call yet this season.</div>
  }
  return (
    <div className="nfl-model-grid">
      <section className="nfl-model-card">
        <div className="nfl-model-card__head">
          <span className="nfl-model-label">Model calls on standard lines</span>
          <span className="nfl-model-muted">one per player, game and market</span>
        </div>
        <div className="nfl-model-card__body">
          <div className="nfl-model-headline">
            <span className={`nfl-model-big ${signalClass(calls.signal)}`}>{pct(calls.hitRate ?? 0)}</span>
            <span className="nfl-model-dim">
              {calls.standardError !== null && <>&plusmn; {(calls.standardError * 100).toFixed(1)} </>}
              on {calls.calls.toLocaleString()} calls
            </span>
            <span className="nfl-model-muted">vs {pct(breakEven)} break-even</span>
          </div>
          <div className="nfl-model-rates">
            {data.byMarket.map((row) => (
              <RateRow key={row.market} label={MARKET_LABELS[row.market] ?? row.market} row={row} breakEven={breakEven} />
            ))}
          </div>
          <p className="nfl-model-note">
            Red marks a rate more than 2 SE below break-even, green one more than 2 SE above. This replays today&apos;s
            code on past weeks, so it is not a frozen record; the ranking check above is. {coverage.settled.toLocaleString()}{' '}
            of {coverage.loaded.toLocaleString()} pre-kickoff lines settled; {coverage.unsettleableSegment.toLocaleString()}{' '}
            half, quarter or season lines cannot be, and {coverage.voidDnp.toLocaleString()} were voided when the player sat.
          </p>
        </div>
      </section>
      <section className="nfl-model-card">
        <div className="nfl-model-card__head">
          <span className="nfl-model-label">Hit rate by edge</span>
          <span className="nfl-model-muted">does a bigger edge hit more?</span>
        </div>
        <div className="nfl-model-card__body">
          <div className="nfl-model-rates">
            {data.byEdge.map((row) => <RateRow key={row.bucket} label={row.label} row={row} breakEven={breakEven} />)}
          </div>
          <p className="nfl-model-note">
            Edge is the projection minus the line, as a share of the market&apos;s median standard line. If the edge
            carried information, the larger buckets would hit more often. The white mark on each bar is the{' '}
            {pct(breakEven)} break-even.
          </p>
        </div>
      </section>
    </div>
  )
}
