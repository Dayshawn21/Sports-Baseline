import { useState } from 'react'
import type { TrackCalibrationSeries } from '~/types/tennis'
import { calibrationPoints } from '~/utils/trackRecord'

type Source = TrackCalibrationSeries['source']

const SOURCE_LABELS: Record<Source, string> = { ensemble: 'Ensemble', market: 'Market', ml: 'LightGBM v6' }
const BOX = { left: 30, right: 310, top: 10, bottom: 250 }
const TICKS = [0, 0.5, 1]

export default function ModelCalibrationChart({ series }: { series: TrackCalibrationSeries[] }) {
  const [source, setSource] = useState<Source>('ensemble')
  const bins = series.find((s) => s.source === source)?.bins ?? []
  const points = calibrationPoints(bins, BOX)
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
      {points.length === 0
        ? <div className="tennis-model-empty tennis-model-chart-empty">No ATP or WTA match has every component and a market price yet.</div>
        : (
          <svg className="tennis-model-calibration" viewBox="0 0 320 280" role="img"
            aria-label={`${SOURCE_LABELS[source]} predicted versus actual p1 win rate`}>
            <line x1={BOX.left} y1={BOX.bottom} x2={BOX.right} y2={BOX.bottom} className="axis" />
            <line x1={BOX.left} y1={BOX.top} x2={BOX.left} y2={BOX.bottom} className="axis" />
            <line x1={BOX.left} y1={BOX.bottom} x2={BOX.right} y2={BOX.top} className="ideal" />
            {TICKS.map((t) => (
              <g key={t}>
                <text x={BOX.left + t * (BOX.right - BOX.left)} y={BOX.bottom + 16}
                  textAnchor={t === 0 ? 'start' : t === 1 ? 'end' : 'middle'}>{`${t * 100}%`}</text>
                <text x={BOX.left - 6} y={BOX.bottom - t * (BOX.bottom - BOX.top) + 4} textAnchor="end">{t * 100}</text>
              </g>
            ))}
            <polyline className="series" points={points.map((p) => `${p.x},${p.y}`).join(' ')} />
            {points.map((p) => (
              <circle key={p.bin.low} cx={p.x} cy={p.y} r={p.r} className="dot">
                <title>{`${Math.round(p.bin.low * 100)}-${Math.round(p.bin.high * 100)}%: predicted ${(p.bin.meanPredicted * 100).toFixed(0)}%, won ${(p.bin.actualRate * 100).toFixed(0)}% of ${p.bin.n}`}</title>
              </circle>
            ))}
          </svg>
        )}
      <p className="tennis-model-note">
        ATP and WTA, {matches.toLocaleString()} matches. Predicted p1 win chance (x) against the actual win rate (y)
        in 10-point bins; dot size is the bin&apos;s match count. The dashed line is perfect calibration.
      </p>
    </div>
  )
}
