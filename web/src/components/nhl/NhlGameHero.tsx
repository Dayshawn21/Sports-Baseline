import type { NhlGameDetail } from '~/types/nhl'
import { nhlBookLabel, nhlGameState, nhlMarketCells, nhlMarketProbability, nhlTimeLabel, type NhlMarketCell } from '~/utils/nhlGame'

export function NhlGameHero({ game }: { game: NhlGameDetail }) {
  const scored = game.status === 'completed' && game.awayScore !== null && game.homeScore !== null
  return <div className="nfl-game-hero" role="group" aria-label="Teams and score">
    <div className="nfl-game-hero__team is-away">
      <span className="nfl-game-badge" aria-hidden="true">{game.awayTeam}</span>
      <div><strong>{game.awayTeamName}</strong><small>Away</small></div>
    </div>
    <div className="nfl-game-hero__mid">
      {scored && <span className="nhl-game-score" aria-label={`${game.awayTeam} ${game.awayScore}, ${game.homeTeam} ${game.homeScore}`}>
        <span>{game.awayScore}</span><span>{game.homeScore}</span>
      </span>}
    </div>
    <div className="nfl-game-hero__team is-home">
      <span className="nfl-game-badge" aria-hidden="true">{game.homeTeam}</span>
      <div><strong>{game.homeTeamName}</strong><small>Home</small></div>
    </div>
  </div>
}

function MarketCell({ cell }: { cell: NhlMarketCell }) {
  return <div>
    <dt>{cell.label}</dt>
    <dd><strong>{cell.value}</strong><span>{cell.detail}</span>
      {cell.book !== null && <small>{nhlBookLabel(cell.book)}{cell.fetchedAt !== null && <>
        {' / '}<time dateTime={cell.fetchedAt}>{nhlTimeLabel(cell.fetchedAt, true)}</time>
      </>}</small>}
    </dd>
  </div>
}

export function NhlGameMarket({ game }: { game: NhlGameDetail }) {
  const probability = nhlMarketProbability(game)
  const missing = game.moneyline === null && game.spread === null && game.total === null
  return <section className="nfl-game-card" aria-label="Market">
    <div className="nfl-game-card__head"><h2 className="nfl-game-label">Market</h2><span className="nfl-game-caveat">Stored prices / OT and shootout included</span></div>
    {missing && <p className="nfl-game-note">No book odds stored for this game.</p>}
    <dl className="nhl-market-grid">{nhlMarketCells(game).map(cell => <MarketCell key={cell.label} cell={cell} />)}</dl>
    <dl className="nhl-market-probability"><MarketCell cell={probability} /></dl>
    {nhlGameState(game, new Date()).state === 'started' && <p className="nfl-game-note">Scores update after the game.</p>}
  </section>
}
