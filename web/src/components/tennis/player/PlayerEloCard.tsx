import type { PlayerDetail } from '~/types/tennis'
import { chartSurface, eloChart } from '~/utils/tennisPlayer'

const BOX = { left: 44, right: 596, top: 14, bottom: 150 }
const SURFACE_LABELS = { hard: 'Hard', clay: 'Clay', grass: 'Grass' }

const rating = (value: number | null) => (value == null ? '—' : Math.round(value).toString())

export default function PlayerEloCard({ player }: { player: PlayerDetail }) {
  const { elo } = player
  const surface = chartSurface(player.nextMatch?.surface)
  const chart = eloChart(elo.history, ['overall', surface], BOX)

  if (!chart) {
    return (
      <div className="tennis-match-empty">
        No ELO rating stored for {player.name}. TennisAbstract ratings start 2026-01-05 and cover ranked players.
      </div>
    )
  }

  const change = elo.change == null ? null : `${elo.change >= 0 ? '+' : ''}${Math.round(elo.change)} since ${elo.history[0]?.asOf}`
  const rank = elo.tourRank != null ? `tour rank by ELO #${elo.tourRank} of ${elo.tourRankOf}` : null
  const points = (key: string) => chart.series[key].map((p) => `${p.x},${p.y}`).join(' ')
  const last = chart.series.overall.at(-1)
  const drawsLines = chart.series.overall.length > 1

  return (
    <div className="tennis-match-card tennis-player-elo">
      <div className="tennis-player-elo__label">ELO · overall</div>
      <div className="tennis-player-elo__big">{rating(elo.overall)}</div>
      <div className="tennis-player-elo__delta">{[change, rank].filter(Boolean).join(' · ') || 'One snapshot so far'}</div>

      <svg className="tennis-player-elo__chart" viewBox="0 0 600 172" role="img"
        aria-label={`ELO over time, overall and ${SURFACE_LABELS[surface].toLowerCase()}`}>
        {chart.ticks.map((t) => (
          <g key={t.value}>
            <line x1={BOX.left} y1={t.y} x2={BOX.right} y2={t.y} className="grid" />
            <text x={0} y={t.y + 4}>{t.value}</text>
          </g>
        ))}
        {chart.series[surface].length > 1 && <polyline className="surface" points={points(surface)} />}
        {chart.series.overall.length > 1 && <polyline className="overall" points={points('overall')} />}
        {last && <circle cx={last.x} cy={last.y} r={4} className="dot" />}
        {chart.dates.map((d, i) => (
          <text key={d.label} x={d.x} y={168} textAnchor={chart.dates.length === 1 ? 'middle' : i === 0 ? 'start' : 'end'}>{d.label}</text>
        ))}
      </svg>
      <div className="tennis-player-elo__legend">
        {drawsLines && `Solid: overall · dashed: ${SURFACE_LABELS[surface].toLowerCase()}. `}
        {elo.history.length} TennisAbstract snapshot{elo.history.length === 1 ? '' : 's'}, latest {elo.asOf}.
      </div>

      <div className="tennis-player-elo__surfaces">
        {([['Overall', elo.overall], ['Hard', elo.hard], ['Clay', elo.clay], ['Grass', elo.grass]] as const).map(([label, value]) => (
          <div key={label}>
            <div className="tennis-player-elo__label">{label}</div>
            <div className="tennis-player-elo__value">{rating(value)}</div>
          </div>
        ))}
      </div>
    </div>
  )
}
