import type { CSSProperties } from 'react'
import { Link } from 'react-router-dom'
import '~/components/nfl/nfl-prop-card.css'
import { useNflLineOnlyProps } from '~/hooks/useNfl'
import { marketLabel } from '~/utils/nflLabels'
import { lineOnlyBars, lineOnlyGroups, mainRung, type NflLineOnlyRow } from '~/utils/nflLineOnly'
import type { NflPositionFilter } from '~/utils/nflPositions'

function rungLabel(line: number, oddsType: string | null): string {
  return oddsType && oddsType !== 'standard' ? `${line} ${oddsType}` : `${line}`
}

function Bars({ row }: { row: NflLineOnlyRow }) {
  const { bars, linePct } = lineOnlyBars(row)
  if (!bars.length) return <span className="nfl-prop-card__no-history">No earlier games</span>
  const style = linePct === null ? undefined : { '--line': `${linePct}%` } as CSSProperties
  return <span className={`nfl-prop-card__bars${linePct === null ? '' : ' has-line'}`} style={style} aria-label={`Last ${bars.length} games`}>
    {bars.map((bar, index) => <span key={index} className={`is-${bar.vsLine ?? 'none'}`} style={{ '--h': `${bar.heightPct}%` } as CSSProperties} title={`${bar.value} vs ${bar.opponentTeam ?? '--'}`} />)}
  </span>
}

function Card({ row, market }: { row: NflLineOnlyRow, market: string }) {
  const main = mainRung(row)
  const others = row.rungs.filter(rung => rung !== main)
  // Oldest to newest, the same order as the bars above it.
  const values = [...row.recent].reverse().map(game => game.value ?? '--').join(' · ')
  return <article className="nfl-prop-card nfl-line-only-card">
    <span className="nfl-prop-card__who">
      <span className="nfl-prop-card__badge" aria-hidden="true">{row.position ?? '--'}</span>
      <span className="nfl-prop-card__name">
        <strong><Link to={`/nfl/player/${row.playerId}`}>{row.playerName}</Link></strong>
        <small>{marketLabel(market)}</small>
      </span>
    </span>
    <span className="nfl-prop-card__value">
      <small>Line</small>
      <b>{main.line}</b>
      <small>{main.oddsType === 'standard' ? 'standard' : main.oddsType ?? ''}</small>
    </span>
    {others.length > 0 && <span className="nfl-line-only-card__rungs">Also {others.map(rung => rungLabel(rung.line, rung.oddsType)).join(' · ')}</span>}
    <Bars row={row} />
    <span className="nfl-prop-card__foot">
      <span className="nfl-prop-card__sample" title="Last games, oldest to newest">{values || 'No earlier games'}</span>
      <span>{row.count ? `over ${row.overCount} of ${row.count}` : ''}</span>
    </span>
  </article>
}

/** Item 35: stored line-only markets with recent results. Display only: no projection, edge, rank or signal color. */
export function NflLineOnlyProps({ gameId, position }: { gameId: number, position: NflPositionFilter }) {
  const query = useNflLineOnlyProps(gameId)
  const groups = query.data ? lineOnlyGroups(query.data.lines, position) : []
  if (query.isSuccess && groups.length === 0) return null
  return <section className="nfl-line-only" aria-label="Other lines">
    <h3 className="nfl-game-label">Other lines <small>not modelled · recent results only</small></h3>
    {query.isLoading && <p className="nfl-line-only__status">Loading other lines...</p>}
    {query.isError && <p className="nfl-line-only__status">Other lines could not load.</p>}
    {groups.map(group => <div key={group.market} className="nfl-line-only__market">
      <h4>{marketLabel(group.market)}</h4>
      <div className="nfl-prop-grid">{group.rows.map(row => <Card key={row.playerId} row={row} market={group.market} />)}</div>
    </div>)}
  </section>
}
