import { Link } from 'react-router-dom'
import '~/components/nfl/nfl-slate-card.css'
import type { NbaSlateCardCell, NbaSlateCardModel, NbaSlateCardTeam } from '~/utils/nbaSlate'

function Team({ team, side }: { team: NbaSlateCardTeam, side: 'away' | 'home' }) {
  return <div className={`nfl-slate-card__team is-${side}`} title={team.name}>
    <span className="nfl-slate-card__badge" aria-hidden="true">{team.code}</span>
    <div><strong>{team.code}</strong><small>{team.record}</small></div>
  </div>
}

function Middle({ card }: { card: NbaSlateCardModel }) {
  if (card.away.score === null || card.home.score === null) return <span className="nfl-slate-card__at">@</span>
  return <div className="nfl-slate-card__score">
    <span className={card.away.lost ? 'is-loser' : ''}>{card.away.score}</span>
    <span className="nfl-slate-card__at">Final</span>
    <span className={card.home.lost ? 'is-loser' : ''}>{card.home.score}</span>
  </div>
}

function Cells({ cells }: { cells: NbaSlateCardCell[] }) {
  return <div className="nfl-slate-card__market">
    {cells.map(cell => <div key={cell.label}>
      <span className="nfl-slate-card__label">{cell.label}</span>
      <b>{cell.value}</b>
      {cell.detail !== null && <span className="nfl-slate-card__move">{cell.detail}</span>}
    </div>)}
  </div>
}

function WinBar({ card }: { card: NbaSlateCardModel }) {
  if (card.winBar === null) return null
  return <>
    <div className="nfl-slate-card__winbar" aria-hidden="true"><i style={{ width: `${card.winBar.away}%` }} /></div>
    <div className="nfl-slate-card__winbar-labels">
      <span>{card.away.code} {card.winBar.away}%</span><span>{card.winBar.home}% {card.home.code}</span>
    </div>
  </>
}

function Body({ card }: { card: NbaSlateCardModel }) {
  if (card.state === 'final') {
    return card.final === null ? <div className="nfl-slate-card__empty">No closing lines stored</div> : <Cells cells={card.final} />
  }
  if (card.state === 'off') return <div className="nfl-slate-card__empty">{card.stateLabel}: no market shown</div>
  return <>
    <WinBar card={card} />
    {card.market === null ? <div className="nfl-slate-card__empty">No market odds stored</div> : <Cells cells={card.market} />}
    {card.state === 'started' && <div className="nfl-slate-card__empty">Scores load the morning after the game</div>}
  </>
}

/** One NBA game on the slate; the whole card links to the game page. Display only, never green. */
export function NbaSlateGameCard({ card }: { card: NbaSlateCardModel }) {
  return <Link className={`nfl-slate-card is-${card.state}`} to={`/nba/game/${card.gameId}`}
    aria-label={`${card.away.code} at ${card.home.code}, open game page`}>
    <div className="nfl-slate-card__meta">
      <span>{card.tip}</span>
      {card.stateLabel !== null && <span className="nfl-slate-card__tags"><span className="nfl-slate-card__tag">{card.stateLabel}</span></span>}
    </div>
    <div className="nfl-slate-card__teams"><Team team={card.away} side="away" /><Middle card={card} /><Team team={card.home} side="home" /></div>
    <Body card={card} />
    <div className="nfl-slate-card__foot"><span>{card.props}</span><span className="nfl-slate-card__open">Open game →</span></div>
  </Link>
}
