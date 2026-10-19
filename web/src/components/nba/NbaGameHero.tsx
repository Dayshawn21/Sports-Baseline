import type { NbaGameDetail } from '~/types/nba'
import type { NbaSlateCardModel, NbaSlateCardTeam } from '~/utils/nbaSlate'
import { nbaGameMarket } from '~/utils/nbaGame'

function Team({ team, side }: { team: NbaSlateCardTeam, side: 'away' | 'home' }) {
  return <div className={`nfl-game-hero__team is-${side}`}>
    <span className="nfl-game-badge" aria-hidden="true">{team.code}</span>
    <div><strong>{team.name}</strong><small>{team.record}</small></div>
  </div>
}

function Score({ card }: { card: NbaSlateCardModel }) {
  if (card.away.score === null || card.home.score === null) return null
  return <span className="nba-game-score">
    <span className={card.away.lost ? 'is-loser' : ''}>{card.away.score}</span>
    <span className={card.home.lost ? 'is-loser' : ''}>{card.home.score}</span>
  </span>
}

/** Supporting team records and final score, read from the slate card model. */
export function NbaGameHero({ card }: { card: NbaSlateCardModel }) {
  return <div className="nfl-game-hero" role="group" aria-label="Team records and score">
    <Team team={card.away} side="away" />
    <div className="nfl-game-hero__mid">
      <Score card={card} />
    </div>
    <Team team={card.home} side="home" />
  </div>
}

/** Market only: NBA has no model row until 20g. */
function MarketBlock({ detail }: { detail: NbaGameDetail }) {
  const market = nbaGameMarket(detail)
  return <section className="nfl-game-card" aria-label="Market">
    <div className="nfl-game-card__head"><h2 className="nfl-game-label">Market</h2><span className="nfl-game-caveat">Latest stored price</span></div>
    <div className="nfl-game-mm">
      <div /><div className="nfl-game-label">Spread</div><div className="nfl-game-label">Win probability</div><div className="nfl-game-label">Total</div>
      <div className="nfl-game-label">Market</div>
      {market ? [market.spread, market.winProbability, market.total].map((cell, index) =>
        <div key={index}><span className="nfl-game-big">{cell.value}</span><small>{cell.detail}</small></div>)
        : <div className="nfl-game-mm__empty">No book odds stored for this game yet.</div>}
    </div>
  </section>
}

function ClosingBlock({ card }: { card: NbaSlateCardModel }) {
  return <section className="nfl-game-card" aria-label="Closing lines">
    <div className="nfl-game-card__head"><h2 className="nfl-game-label">Closing lines</h2><span className="nfl-game-caveat">Last line before tip-off</span></div>
    {card.final === null
      ? <p className="nfl-game-note">No closing lines stored</p>
      : <div className="nba-game-cells">{card.final.map(cell => <div key={cell.label}>
        <span className="nfl-game-label">{cell.label}</span>
        <span className="nfl-game-big">{cell.value}</span>
        {cell.detail !== null && <small>{cell.detail}</small>}
      </div>)}</div>}
  </section>
}

/** The block under the hero, by game state, mirroring the slate card's body. */
export function NbaGameMarket({ detail, card }: { detail: NbaGameDetail, card: NbaSlateCardModel }) {
  if (card.state === 'final') return <ClosingBlock card={card} />
  if (card.state === 'off') return <p className="nfl-game-empty">{card.stateLabel}: no market shown</p>
  return <>
    <MarketBlock detail={detail} />
    {card.state === 'started' && <p className="nfl-game-note">Scores load the morning after the game.</p>}
  </>
}
