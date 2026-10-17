import { Link } from 'react-router-dom'
import type { NflSlateCardCell, NflSlateCardModel, NflSlateCardTeam } from '~/utils/nflSlate'
import './nfl-slate-card.css'

function Team({ team, side }: { team: NflSlateCardTeam, side: 'away' | 'home' }) {
  const detail = team.rest === null ? team.record : `${team.record} · ${team.rest}`
  return <div className={`nfl-slate-card__team is-${side}`}>
    <span className="nfl-slate-card__badge" aria-hidden="true">{team.code}</span>
    <div><strong>{team.code}</strong><small>{detail}</small></div>
  </div>
}

function Middle({ card }: { card: NflSlateCardModel }) {
  if (card.away.score === null || card.home.score === null) return <span className="nfl-slate-card__at">@</span>
  return <div className="nfl-slate-card__score">
    <span className={card.away.lost ? 'is-loser' : ''}>{card.away.score}</span>
    <span className="nfl-slate-card__at">Final</span>
    <span className={card.home.lost ? 'is-loser' : ''}>{card.home.score}</span>
  </div>
}

function Tags({ card }: { card: NflSlateCardModel }) {
  const injuries = card.injuries
  return <span className="nfl-slate-card__tags">
    {card.state === 'live' && <span className="nfl-slate-card__live">Live</span>}
    {card.state === 'final' && <span className="nfl-slate-card__tag">Final</span>}
    {injuries !== null && injuries.out > 0 && <span className="nfl-slate-card__tag is-out">{injuries.out} Out</span>}
    {injuries !== null && injuries.doubtful > 0 && <span className="nfl-slate-card__tag is-caution">{injuries.doubtful} D</span>}
    {injuries !== null && injuries.questionable > 0 && <span className="nfl-slate-card__tag is-caution">{injuries.questionable} Q</span>}
    {card.qbChange.map(team => <span key={`qb-${team}`} className="nfl-slate-card__tag is-caution">QB change: {team}</span>)}
    {card.shortWeek.map(team => <span key={team} className="nfl-slate-card__tag">Short week: {team}</span>)}
  </span>
}

function Cells({ cells }: { cells: NflSlateCardCell[] }) {
  return <div className="nfl-slate-card__market">
    {cells.map(cell => <div key={cell.label}>
      <span className="nfl-slate-card__label">{cell.label}</span>
      <b>{cell.value}</b>
      {cell.detail !== null && <span className="nfl-slate-card__move">{cell.detail}</span>}
    </div>)}
  </div>
}

function WinBar({ card }: { card: NflSlateCardModel }) {
  if (card.winBar === null) return null
  return <>
    <div className="nfl-slate-card__winbar" aria-hidden="true"><i style={{ width: `${card.winBar.away}%` }} /></div>
    <div className="nfl-slate-card__winbar-labels">
      <span>{card.away.code} {card.winBar.away}%</span><span>{card.winBar.home}% {card.home.code}</span>
    </div>
  </>
}

function Model({ card }: { card: NflSlateCardModel }) {
  if (card.model === null) return <div className="nfl-slate-card__model">Model unavailable for this game</div>
  return <div className="nfl-slate-card__model">
    <span className="nfl-slate-card__label">Model</span>
    <span>{card.model.spread}</span><span>{card.model.total}</span><span>{card.model.winProbability}</span>
    <span className="nfl-slate-card__caveat">Not a pick</span>
  </div>
}

function TopProps({ card }: { card: NflSlateCardModel }) {
  if (card.rateableCount + card.otherCount === 0) return <div className="nfl-slate-card__empty">No prop lines stored for this game yet</div>
  if (card.topProps.length === 0) return <div className="nfl-slate-card__empty">No rateable props</div>
  return <div className="nfl-slate-card__teaser">
    {card.state === 'live' && <div className="nfl-slate-card__closed">Lines closed at kickoff</div>}
    {card.topProps.map(prop => <div key={prop.lineId} className="nfl-slate-card__prop">
      <strong>{prop.playerName}</strong><span>{prop.market}</span>
      <span className="nfl-slate-card__num is-dim">{prop.line}</span><span className="nfl-slate-card__num">{prop.edge}</span>
    </div>)}
  </div>
}

function Body({ card }: { card: NflSlateCardModel }) {
  if (card.state === 'final') {
    return card.final === null
      ? <div className="nfl-slate-card__empty">Final score not loaded yet</div>
      : <Cells cells={card.final} />
  }
  return <>
    <WinBar card={card} />
    {card.market === null ? <div className="nfl-slate-card__empty">No market odds stored</div> : <Cells cells={card.market} />}
    {card.bestSpread !== null && <div className="nfl-slate-card__best">{card.bestSpread}</div>}
    <Model card={card} />
    <TopProps card={card} />
  </>
}

/** One game on the slate; the whole card links to the game page. Display only, never green. */
export function NflSlateGameCard({ card }: { card: NflSlateCardModel }) {
  const counts = `${card.rateableCount} rateable props · ${card.otherCount} not rateable`
  return <Link className={`nfl-slate-card is-${card.state}`} to={`/nfl/game/${card.gameId}`}
    aria-label={`${card.away.code} at ${card.home.code}, open game page`}>
    <div className="nfl-slate-card__meta"><span>{card.state === 'final' ? card.kickoff : card.conditions}</span><Tags card={card} /></div>
    <div className="nfl-slate-card__teams"><Team team={card.away} side="away" /><Middle card={card} /><Team team={card.home} side="home" /></div>
    <Body card={card} />
    <div className="nfl-slate-card__foot"><span>{card.state === 'final' ? 'Final' : counts}</span><span className="nfl-slate-card__open">Open game →</span></div>
  </Link>
}
