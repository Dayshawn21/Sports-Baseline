import type { NflGameDetail, NflGameNotes, NflSlateGame, NflTeamContext } from '~/types/nfl'
import { conditionsLabel, gameMarket, marketImpliedPoints, recordLabel } from '~/utils/nflGame'
import { NFL_GAME_MODEL_CAVEAT, nflGameModelSummary, qbChangeText, qbChanges, type NflGameModelCell } from '~/utils/nflGameModel'

const VENUE_LABELS: Record<string, string> = { dome: 'Dome', outdoor: 'Outdoor', retractable: 'Retractable roof' }
const POINTS = new Intl.NumberFormat('en-US', { minimumFractionDigits: 1, maximumFractionDigits: 2 })

/** `context` is undefined while the slate loads, so no record is claimed before it arrives. */
function Team({ code, context, side }: { code: string, context: NflTeamContext | null | undefined, side: 'away' | 'home' }) {
  return <div className={`nfl-game-hero__team is-${side}`}>
    <span className="nfl-game-badge" aria-hidden="true">{code}</span>
    <div><strong>{code}</strong><small>{context === undefined ? null : recordLabel(context)}</small></div>
  </div>
}

export function NflGameHero({ detail, game }: { detail: NflGameDetail, game: NflSlateGame | null }) {
  const venue = game ? VENUE_LABELS[game.weather.venueType] ?? game.weather.venueType : null
  return <div className="nfl-game-hero" role="group" aria-label="Team records and conditions">
    <Team code={detail.awayTeam} context={game?.awayContext} side="away" />
    <div className="nfl-game-hero__mid">
      {game && <span>{venue} · {conditionsLabel(game.weather)}</span>}
    </div>
    <Team code={detail.homeTeam} context={game?.homeContext} side="home" />
  </div>
}

function ModelCell({ cell }: { cell: NflGameModelCell }) {
  return <div className="is-model"><span className="nfl-game-big">{cell.model}</span><small>{cell.gap ?? 'No market to compare'}</small></div>
}

/** Market in the primary color; the team-strength model muted beneath it, never a pick. */
export function NflGameMarketBlock({ game, notes }: { game: NflSlateGame, notes: NflGameNotes | undefined }) {
  const market = gameMarket(game.odds, game.homeTeam, game.awayTeam)
  const model = nflGameModelSummary(game.model, game.odds, game.homeTeam, game.awayTeam)
  const implied = marketImpliedPoints(game.odds)
  return <section className="nfl-game-card" aria-label="Market and model">
    <div className="nfl-game-card__head"><h2 className="nfl-game-label">Market and model</h2><span className="nfl-game-caveat">Model is context, not a pick</span></div>
    <div className="nfl-game-mm">
      <div /><div className="nfl-game-label">Spread</div><div className="nfl-game-label">Win probability</div><div className="nfl-game-label">Total</div>
      <div className="nfl-game-label">Market</div>
      {market ? [market.spread, market.winProbability, market.total].map((cell, index) =>
        <div key={index}><span className="nfl-game-big">{cell.value}</span><small>{cell.detail}</small></div>)
        : <div className="nfl-game-mm__empty">No book odds stored for this game yet.</div>}
      <div className="nfl-game-label">Model</div>
      {model ? <><ModelCell cell={model.spread} /><ModelCell cell={model.winProbability} /><ModelCell cell={model.total} /></>
        : <div className="nfl-game-mm__empty">Model unavailable for this game.</div>}
    </div>
    <div className="nfl-game-implied" role="group" aria-label="Market-implied points">
      <div><h3>Market-implied points</h3><p>{implied ? `Derived from ${game.odds?.book}'s displayed spread and total.` : 'Requires a valid spread and total from the displayed book.'}</p></div>
      {implied && <dl><div><dt>{game.awayTeam}</dt><dd>{POINTS.format(implied.away)}</dd></div><div><dt>{game.homeTeam}</dt><dd>{POINTS.format(implied.home)}</dd></div></dl>}
    </div>
    {model && qbChanges(notes).map(change => <p key={change.team} className="nfl-game-note is-qb-change">{qbChangeText(change)}</p>)}
    {model && <p className="nfl-game-note">{NFL_GAME_MODEL_CAVEAT}</p>}
  </section>
}
