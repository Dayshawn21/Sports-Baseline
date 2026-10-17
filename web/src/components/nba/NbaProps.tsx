import '~/components/nfl/nfl-prop-card.css'
import { NbaRecentBars } from '~/components/nba/NbaLineOnlyProps'
import { useNbaProps } from '~/hooks/useNba'
import { nbaMarketLabel, nbaRecentValueLabel } from '~/utils/nbaLineOnly'
import { nbaPropGroups, type NbaPropCard } from '~/utils/nbaProps'

function Card({ card, market }: { card: NbaPropCard, market: string }) {
  const values = [...card.recent].reverse().map(game => nbaRecentValueLabel(market, game.value)).join(' · ')
  return <article className="nfl-prop-card nfl-line-only-card nba-prop-card">
    <span className="nfl-prop-card__who">
      <span className="nfl-prop-card__badge" aria-hidden="true">{card.team ?? '--'}</span>
      <span className="nfl-prop-card__name">
        <strong>{card.playerName}</strong>
        <small>{card.position ? `${card.position} · ` : ''}{nbaMarketLabel(market)}</small>
      </span>
    </span>
    <span className="nfl-prop-card__value">
      <small>Line</small>
      <b>{card.main.line}</b>
      <small>{card.main.oddsType ?? ''}</small>
    </span>
    {card.also.length > 0 && <span className="nfl-line-only-card__rungs">Also {card.also.join(', ')}</span>}
    {card.projectionRow && <span className="nba-prop-card__projection">
      <span>{card.projectionRow.projection}</span>
      <span>{card.projectionRow.gap}</span>
      {card.projectionRow.probability && <span>{card.projectionRow.probability}</span>}
    </span>}
    {card.flagText && <span className="nba-prop-card__flag">{card.flagText}</span>}
    <NbaRecentBars row={card} market={market} />
    <span className="nfl-prop-card__foot">
      <span className="nfl-prop-card__sample" title="Last games, oldest to newest">{values || 'No earlier games'}</span>
      <span>{card.count ? `over ${card.overCount} of ${card.count}` : ''}</span>
    </span>
  </article>
}

/** Modelled PrizePicks lines with the reference projection (20g2). Gray: no pick, rank or signal color until 20g4. */
export function NbaProps({ gameId }: { gameId: number }) {
  const query = useNbaProps(gameId)
  const groups = query.data ? nbaPropGroups(query.data.lines) : []
  if (query.isSuccess && groups.length === 0) return null
  return <section className="nfl-line-only nba-props" aria-label="Props">
    <h3 className="nfl-game-label">Props <small>reference projection · gray until the ranking check adopts a slice</small></h3>
    {query.isLoading && <p className="nfl-line-only__status">Loading props...</p>}
    {query.isError && <p className="nfl-line-only__status">Props could not load.</p>}
    {groups.map(group => <div key={group.market} className="nfl-line-only__market">
      <h4>{nbaMarketLabel(group.market)}</h4>
      <div className="nfl-prop-grid">{group.cards.map(card => <Card key={card.playerId} card={card} market={group.market} />)}</div>
    </div>)}
  </section>
}
