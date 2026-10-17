import { useState } from 'react'
import type { MatchDetail, MatchOddsMarket } from '~/types/tennis'
import { useMatchOddsHistory } from '~/hooks/useMatchOddsHistory'
import { fmtStartCT } from '~/utils/format'
import { fmtPct } from '~/utils/odds'
import {
  bookLabel,
  buildMovementSeries,
  chartScale,
  preferredSeries,
  project,
  seriesForSide,
  summarizeMove,
  type BookSeries,
  type ChartScale,
} from '~/utils/matchOdds'
import { heroSide, sideView } from '~/utils/tennisMatch'

const MARKETS: Array<[MatchOddsMarket, string]> = [['moneyline', 'Moneyline'], ['total_games', 'Total games']]
const SECONDARY_COLORS = ['var(--chart-mid)', 'var(--chart-low)']

function lastName(name: string): string {
  return name.split(/\s+/).filter(Boolean).pop() ?? name
}

function colorFor(book: string, primary: string | undefined, index: number): string {
  return book === primary ? 'var(--text-primary)' : SECONDARY_COLORS[index % SECONDARY_COLORS.length]
}

function fmtValue(market: MatchOddsMarket, value: number): string {
  return market === 'moneyline' ? fmtPct(value) : value.toFixed(1)
}

function Plot({ series, scale, model, market, primary }: {
  series: BookSeries[]
  scale: ChartScale
  model: number | null
  market: MatchOddsMarket
  primary: string | undefined
}) {
  const ticks = [scale.vMax, (scale.vMax + scale.vMin) / 2, scale.vMin]
  const modelY = model != null ? project(scale, new Date(scale.tMin).toISOString(), model).y * 100 : null
  return (
    <div className="tennis-match-plot">
      {ticks.map((value, i) => (
        <span key={i} className="tennis-match-plot__tick" style={{ top: `${i * 50}%` }}>{fmtValue(market, value)}</span>
      ))}
      <svg viewBox="0 0 100 100" preserveAspectRatio="none" role="img" aria-label={`${market === 'moneyline' ? 'Moneyline' : 'Total games'} price movement by book`}>
        {[0, 50, 100].map((y) => <line key={y} x1="0" x2="100" y1={y} y2={y} className="tennis-match-plot__grid" vectorEffect="non-scaling-stroke" />)}
        {modelY != null && <line x1="0" x2="100" y1={modelY} y2={modelY} className="tennis-match-plot__model" vectorEffect="non-scaling-stroke" />}
        {series.map((s, index) => {
          const color = colorFor(s.book, primary, index)
          const pts = s.points.map((pt) => project(scale, pt.at, pt.value))
          const end = pts[pts.length - 1]
          return (
            <g key={s.book} stroke={color}>
              {pts.length > 1 && <polyline points={pts.map(({ x, y }) => `${x * 100},${y * 100}`).join(' ')} fill="none" strokeWidth={s.book === primary ? 2.5 : 2} vectorEffect="non-scaling-stroke" />}
              {/* A zero-length round-capped line stays a true dot however the SVG stretches. */}
              <line x1={end.x * 100} y1={end.y * 100} x2={end.x * 100} y2={end.y * 100} strokeWidth={8} strokeLinecap="round" vectorEffect="non-scaling-stroke" />
            </g>
          )
        })}
      </svg>
    </div>
  )
}

function Footer({ series, model, market, scale }: { series: BookSeries | null; model: number | null; market: MatchOddsMarket; scale: ChartScale }) {
  const move = series ? summarizeMove(series, model) : null
  let summary = ''
  if (series && move) {
    summary = `${bookLabel(series.book)} ${fmtValue(market, move.open)} → ${fmtValue(market, move.latest)}`
    if (move.direction === 'flat') summary += ' · unchanged against the model'
    else if (move.direction && move.towardModelPts != null) {
      summary += ` · moved ${Math.abs(move.towardModelPts).toFixed(1)} pts ${move.direction === 'toward' ? 'toward' : 'away from'} the model`
    }
  }
  return (
    <div className="tennis-match-plot__foot">
      <span>{fmtStartCT(new Date(scale.tMin).toISOString())}</span>
      <span>{summary}</span>
      <span>{fmtStartCT(new Date(scale.tMax).toISOString())}</span>
    </div>
  )
}

export default function MatchOddsChart({ detail }: { detail: MatchDetail }) {
  const [market, setMarket] = useState<MatchOddsMarket>('moneyline')
  const history = useMatchOddsHistory(detail.matchId, market)
  const side = heroSide(detail)
  const view = sideView(detail, side)
  const isMoneyline = market === 'moneyline'
  const raw = buildMovementSeries(history.data?.rows ?? [], market)
  const series = isMoneyline ? seriesForSide(raw, side) : raw
  const model = isMoneyline ? view.modelProb : null
  const scale = chartScale(series, model != null ? [model] : [], isMoneyline ? 0.04 : 2)
  const primary = preferredSeries(series)

  let body
  if (history.isLoading) body = <div className="tennis-match-plot__note">Loading prices...</div>
  else if (history.isError) body = <div className="tennis-match-plot__note">Prices could not be loaded.</div>
  else if (!scale) body = <div className="tennis-match-plot__note">No stored {isMoneyline ? 'moneyline' : 'total games'} prices for this match.</div>
  else body = <>
    <Plot series={series} scale={scale} model={model} market={market} primary={primary?.book} />
    <Footer series={primary} model={model} market={market} scale={scale} />
  </>

  return (
    <section aria-labelledby="tennis-match-odds">
      <div className="tennis-match-chart-head">
        <h2 id="tennis-match-odds" className="tennis-match-section">
          {isMoneyline ? `Moneyline movement · ${lastName(view.name)} implied` : 'Total games line movement'}
        </h2>
        <div className="tennis-match-seg" role="tablist" aria-label="Market">
          {MARKETS.map(([value, label]) => (
            <button key={value} type="button" role="tab" aria-selected={market === value} className={market === value ? 'is-on' : ''} onClick={() => setMarket(value)}>{label}</button>
          ))}
        </div>
      </div>
      <div className="tennis-match-card tennis-match-chart">
        {scale && (
          <div className="tennis-match-legend">
            {series.map((s, index) => (
              <span key={s.book}><i style={{ background: colorFor(s.book, primary?.book, index) }} />{bookLabel(s.book)}</span>
            ))}
            {model != null && <span><i className="is-dashed" />Model {fmtPct(model)}</span>}
          </div>
        )}
        {body}
      </div>
    </section>
  )
}
