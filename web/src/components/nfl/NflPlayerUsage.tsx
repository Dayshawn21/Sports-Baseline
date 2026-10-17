import type { CSSProperties } from 'react'
import type { NflPlayerDetail } from '~/types/nfl'
import { usageBars, type NflUsageRow } from '~/utils/nflPlayer'

function valueLabel(row: NflUsageRow, value: number | null): string {
  if (value === null) return 'no data'
  return row.stat === 'snap_pct' ? `${Math.round(value * 100)}%` : String(value)
}

function UsageRow({ row }: { row: NflUsageRow }) {
  return <div>
    <div className="nfl-player-usage__head"><span>{row.label}</span><b>{row.average}</b></div>
    <div className="nfl-player-weekbars" role="img" aria-label={`${row.label} by week`}>
      {row.bars.map((bar, index) => <i key={index} className={bar.previousSeason ? 'is-prior' : ''}
        style={{ '--h': `${bar.heightPct}%` } as CSSProperties} title={`Week ${bar.week}: ${valueLabel(row, bar.value)}`} />)}
    </div>
    <div className="nfl-player-weekaxis" aria-hidden="true">{row.bars.map((bar, index) => <span key={index}>{bar.week}</span>)}</div>
  </div>
}

/** Carries, targets and snap share by game; last season's games sit in the darker gray. */
export function NflPlayerUsage({ player }: { player: NflPlayerDetail }) {
  const priorSeason = player.usage.some(game => game.previousSeason) ? ` · ${player.season - 1} in dark gray` : ''
  return <section className="nfl-player-card" aria-label="Usage by week">
    <div className="nfl-player-card__head">
      <span className="nfl-player-label">Usage by week</span>
      <span className="nfl-player-muted">Last {player.usage.length} games{priorSeason}</span>
    </div>
    {player.usage.length === 0
      ? <p className="nfl-player-card__empty">No completed games loaded for this player.</p>
      : <div className="nfl-player-card__body nfl-player-usage">
        {player.usageStats.map(stat => <UsageRow key={stat} row={usageBars(player.usage, stat)} />)}
      </div>}
  </section>
}
