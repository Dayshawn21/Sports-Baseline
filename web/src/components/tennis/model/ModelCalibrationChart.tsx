import { useState } from 'react'
import { CartesianGrid, ReferenceLine, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis, ZAxis } from 'recharts'
import type { TrackCalibrationSeries } from '~/types/tennis'
import { type CalibrationDatum, calibrationChartData } from '~/utils/trackRecord'

type Source = TrackCalibrationSeries['source']

const SOURCE_LABELS: Record<Source, string> = { ensemble: 'Ensemble', market: 'Market', ml: 'LightGBM v6' }
const TICKS = [0, 25, 50, 75, 100]
const AXIS_TICK = { fill: 'var(--text-muted)', fontSize: 11, fontFamily: 'var(--font-mono)' }

function CalibrationTooltip({ active, payload }: { active?: boolean, payload?: { payload: CalibrationDatum }[] }) {
  const datum = payload?.[0]?.payload
  if (!active || datum === undefined) return null
  return <div className="tennis-model-calibration-tip">
    <strong>{datum.range}</strong>
    <span>predicted {datum.predicted.toFixed(0)}%, won {datum.actual.toFixed(0)}%</span>
    <span>{datum.n.toLocaleString()} matches</span>
  </div>
}

export default function ModelCalibrationChart({ series }: { series: TrackCalibrationSeries[] }) {
  const [source, setSource] = useState<Source>('ensemble')
  const bins = series.find((s) => s.source === source)?.bins ?? []
  const data = calibrationChartData(bins)
  const matches = bins.reduce((sum, b) => sum + b.n, 0)

  return (
    <div className="tennis-model-card tennis-model-pad">
      <div className="tennis-model-chart-head">
        <h3 className="tennis-model-subhead">Calibration · {SOURCE_LABELS[source]}</h3>
        <div className="segment-toggle" role="group" aria-label="Calibration source">
          {series.map((s) => (
            <button key={s.source} type="button" className={s.source === source ? 'is-selected' : ''}
              aria-pressed={s.source === source} onClick={() => setSource(s.source)}>
              {SOURCE_LABELS[s.source]}
            </button>
          ))}
        </div>
      </div>
      {data.length === 0
        ? <div className="tennis-model-empty tennis-model-chart-empty">No ATP or WTA match has every component and a market price yet.</div>
        : (
          <div className="tennis-model-calibration" role="img" aria-label={`${SOURCE_LABELS[source]} predicted versus actual p1 win rate`}>
            <ResponsiveContainer width="100%" height={300}>
              <ScatterChart margin={{ top: 10, right: 12, bottom: 4, left: -12 }}>
                <CartesianGrid stroke="var(--border-subtle)" />
                <XAxis type="number" dataKey="predicted" domain={[0, 100]} ticks={TICKS} tickFormatter={(v: number) => `${v}%`}
                  tick={AXIS_TICK} stroke="var(--border-card)" />
                <YAxis type="number" dataKey="actual" domain={[0, 100]} ticks={TICKS} tick={AXIS_TICK} stroke="var(--border-card)" />
                <ZAxis type="number" dataKey="n" range={[20, 160]} />
                <ReferenceLine segment={[{ x: 0, y: 0 }, { x: 100, y: 100 }]} stroke="var(--chart-mid)" strokeDasharray="4 4" ifOverflow="extendDomain" />
                <Tooltip content={<CalibrationTooltip />} cursor={{ stroke: 'var(--border-card)' }} isAnimationActive={false} />
                <Scatter data={data} fill="var(--text-primary)" line={{ stroke: 'var(--text-primary)', strokeWidth: 2 }} isAnimationActive={false} />
              </ScatterChart>
            </ResponsiveContainer>
          </div>
        )}
      <p className="tennis-model-note">
        ATP+WTA all-four sample, {matches.toLocaleString()} matches with ensemble, market, ELO and ML probabilities.
        Predicted p1 win chance (x) against the actual win rate (y)
        in 10-point bins; dot size is the bin&apos;s match count. The dashed line is perfect calibration.
      </p>
    </div>
  )
}
