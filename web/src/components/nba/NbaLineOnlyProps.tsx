import '~/components/nfl/nfl-prop-card.css'
import { MiniBars } from '~/components/shared/MiniBars'
import { useNbaLineOnlyProps } from '~/hooks/useNba'
import { nbaLineOnlyGroups, nbaMarketLabel, nbaRecentValueLabel, type NbaLineOnlyRow } from '~/utils/nbaLineOnly'
import { lineOnlyBars, mainRung } from '~/utils/nflLineOnly'

function rungLabel(line: number, oddsType: string | null): string {
  return oddsType && oddsType !== 'standard' ? `${line} ${oddsType}` : `${line}`
}

/** Recent results as gray bars, oldest to newest, with the standard line dashed. */
export function NbaRecentBars({ row, market }: { row: Parameters<typeof lineOnlyBars>[0], market: string }) {
  return <MiniBars bars={lineOnlyBars(row)} empty="No earlier games" title={bar => `${nbaRecentValueLabel(market, bar.value)} vs ${bar.opponentTeam ?? '--'}`} />
}

function Card({ row, market }: { row: NbaLineOnlyRow, market: string }) {
  const main = mainRung(row)
  const others = row.rungs.filter(rung => rung !== main)
  // Oldest to newest, the same order as the bars above it.
  const values = [...row.recent].reverse().map(game => nbaRecentValueLabel(market, game.value)).join(' · ')
  return <article className="nfl-prop-card nfl-line-only-card">
    <span className="nfl-prop-card__who">
      <span className="nfl-prop-card__badge" aria-hidden="true">{row.team ?? '--'}</span>
      <span className="nfl-prop-card__name">
        <strong>{row.playerName}</strong>
        <small>{row.position ? `${row.position} · ` : ''}{nbaMarketLabel(market)}</small>
      </span>
    </span>
    <span className="nfl-prop-card__value">
      <small>Line</small>
      <b>{main.line}</b>
      <small>{main.oddsType ?? ''}</small>
    </span>
    {others.length > 0 && <span className="nfl-line-only-card__rungs">Also {others.map(rung => rungLabel(rung.line, rung.oddsType)).join(' · ')}</span>}
    <NbaRecentBars row={row} market={market} />
    <span className="nfl-prop-card__foot">
      <span className="nfl-prop-card__sample" title="Last games, oldest to newest">{values || 'No earlier games'}</span>
      <span>{row.count ? `over ${row.overCount} of ${row.count}` : ''}</span>
    </span>
  </article>
}

/** Stored PrizePicks lines with recent results. Display only: no projection, edge, rank or signal color until 20g. */
export function NbaLineOnlyProps({ gameId }: { gameId: number }) {
  const query = useNbaLineOnlyProps(gameId)
  const groups = query.data ? nbaLineOnlyGroups(query.data.lines) : []
  if (query.isSuccess && groups.length === 0) return null
  return <section className="nfl-line-only" aria-label="Other lines">
    <h3 className="nfl-game-label">Other lines <small>not modelled · recent results only</small></h3>
    {query.isLoading && <p className="nfl-line-only__status">Loading lines...</p>}
    {query.isError && <p className="nfl-line-only__status">Lines could not load.</p>}
    {groups.map(group => <div key={group.market} className="nfl-line-only__market">
      <h4>{nbaMarketLabel(group.market)}</h4>
      <div className="nfl-prop-grid">{group.rows.map(row => <Card key={row.playerId} row={row} market={group.market} />)}</div>
    </div>)}
  </section>
}
