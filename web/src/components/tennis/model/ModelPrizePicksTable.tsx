import type { CSSProperties } from 'react'
import type { ModelPrizePicksLinesResponse, TrackLineRow } from '~/types/tennis'
import { marketTitle } from '~/utils/tennisPropBoard'
import { rateRange, signalClass } from '~/utils/trackRecord'

const pct = (value: number) => `${(value * 100).toFixed(1)}%`

const LINE_TYPE_LABELS = { standard: 'Standard', goblin: 'Goblin', demon: 'Demon' }

function RangeCell({ row }: { row: TrackLineRow }) {
  if (row.overRate == null) return <td className="tennis-model-range-cell" />
  const range = rateRange(row.overRate, row.standardError)
  const style = {
    '--p': pct(row.overRate),
    '--lo': range ? pct(range.low) : '0%',
    '--hi': range ? pct(range.high) : '0%',
    '--be': row.breakEven != null ? pct(row.breakEven) : '0%',
  } as CSSProperties
  return (
    <td className="tennis-model-range-cell">
      <div className="tennis-model-range" style={style}
        title={`Over ${pct(row.overRate)}${range ? `, 1 SE ${pct(range.low)} to ${pct(range.high)}` : ''}${row.breakEven != null ? `, break-even ${pct(row.breakEven)}` : ''}`}>
        {range && <span className="rng" />}
        {row.breakEven != null && <span className="be" />}
        <span className="pt" />
      </div>
    </td>
  )
}

export default function ModelPrizePicksTable({ data }: { data: ModelPrizePicksLinesResponse }) {
  if (data.rows.length === 0) {
    return <div className="tennis-model-empty">No PrizePicks line has settled against a final score or box score yet.</div>
  }
  const settled = data.rows.reduce((sum, row) => sum + row.settled, 0)
  return (
    <div className="tennis-model-card tennis-model-pad">
      <div className="tennis-model-scroll">
        <table className="tennis-model-table tennis-model-lines">
          <thead>
            <tr>
              <th>Stat</th><th>Line type</th><th>Settled</th><th>Over</th><th>Under</th><th>Push</th><th>Over hit</th>
              <th className="tennis-model-range-head">Over hit vs break-even</th>
            </tr>
          </thead>
          <tbody>
            {data.rows.map((row) => (
              <tr key={`${row.oddsType}-${row.stat}`}>
                <td>{marketTitle(row.stat)}</td>
                <td><span className={`tennis-model-tag is-${row.oddsType}`}>{LINE_TYPE_LABELS[row.oddsType]}</span></td>
                <td>{row.settled.toLocaleString()}</td>
                <td>{pct(row.overShare)}</td>
                <td>{pct(row.underShare)}</td>
                <td>{pct(row.pushShare)}</td>
                <td className={signalClass(row.signal)}>
                  {row.overRate != null ? pct(row.overRate) : '—'}
                  {row.standardError != null && <span className="tennis-model-se"> ±{pct(row.standardError)}</span>}
                </td>
                <RangeCell row={row} />
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="tennis-model-note">
        {settled.toLocaleString()} closing pre-start lines settled against final scores, or the one box score that
        joins the match. Over hit excludes pushes. The axis runs 0 to 100%: the dot is the over hit rate, the bar is
        ±1 SE, and the dashed amber mark is the per-leg break-even at the app&apos;s assumed payouts. Red marks a rate
        more than 2 SE below break-even. Goblin and demon lines stack several deep per player and move together, so
        they carry no error bar and are never colored. This grades PrizePicks&apos; lines, not the model&apos;s picks.
      </p>
    </div>
  )
}
