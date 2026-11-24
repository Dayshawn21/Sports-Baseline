import type { NhlGameDetail } from '~/types/nhl'
import { nhlBookLabel, nhlGameState, nhlMarketCells, nhlMarketProbability, nhlTimeLabel, type NhlMarketCell } from '~/utils/nhlGame'

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
    {['started', 'pending'].includes(nhlGameState(game, new Date()).state) && <p className="nfl-game-note">Scores update after the game.</p>}
  </section>
}
