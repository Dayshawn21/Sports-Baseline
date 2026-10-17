import type { MouseEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import type { NflSlateRowCell, NflSlateRowModel } from '~/utils/nflSlate'
import './nfl-slate-card.css'
import './nfl-slate-table.css'

function Value({ cell }: { cell: NflSlateRowCell }) {
  return <>{cell.value}{cell.detail !== null && <small>{cell.detail}</small>}</>
}

function Game({ row }: { row: NflSlateRowModel }) {
  const { away, home } = row
  const scored = away.score !== null && home.score !== null
  return <Link to={`/nfl/game/${row.gameId}`} aria-label={`${away.code} at ${home.code}, open game page`}>
    {scored
      ? <><span className={away.lost ? 'is-loser' : ''}>{away.code} {away.score}</span> · <span className={home.lost ? 'is-loser' : ''}>{home.code} {home.score}</span></>
      : `${away.code} @ ${home.code}`}
    <small>{row.state === 'final' ? 'final' : `${away.record} · ${home.record}`}</small>
  </Link>
}

function Notes({ row }: { row: NflSlateRowModel }) {
  const { injuries } = row
  return <span className="nfl-slate-table__tags">
    {injuries !== null && injuries.out > 0 && <span className="nfl-slate-card__tag is-out">{injuries.out} Out</span>}
    {injuries !== null && injuries.doubtful > 0 && <span className="nfl-slate-card__tag is-caution">{injuries.doubtful} D</span>}
    {injuries !== null && injuries.questionable > 0 && <span className="nfl-slate-card__tag is-caution">{injuries.questionable} Q</span>}
    {row.qbChange.map(team => <span key={`qb-${team}`} className="nfl-slate-card__tag is-caution">QB change: {team}</span>)}
    {row.shortWeek.map(team => <span key={team} className="nfl-slate-card__tag">Short week: {team}</span>)}
    {row.state !== 'final' && <span className="nfl-slate-table__conditions">{row.conditions}</span>}
  </span>
}

function Kickoff({ row }: { row: NflSlateRowModel }) {
  if (row.state === 'live') return <><span className="nfl-slate-card__live">Live</span><small>{row.kickoff}</small></>
  return <>{row.kickoff}</>
}

const COLUMNS = ['kickoff', 'game', 'spread', 'total', 'moneyline', 'model', 'props', 'notes']

/** One kickoff window's games, one row each; a row opens its game page. Display only, never green. */
export function NflSlateTable({ rows, label }: { rows: NflSlateRowModel[], label: string }) {
  const navigate = useNavigate()
  const open = (event: MouseEvent, gameId: number) => {
    // The Game link handles its own clicks, so a click on it never navigates twice.
    if (event.target instanceof Element && event.target.closest('a')) return
    navigate(`/nfl/game/${gameId}`)
  }
  return <table className="nfl-slate-table" aria-label={label}>
    <colgroup>{COLUMNS.map(column => <col key={column} className={`is-${column}`} />)}</colgroup>
    <thead><tr>
      <th>Kickoff</th><th>Game</th><th>Spread</th><th>Total</th><th>Moneyline</th>
      <th>Model <small>not a pick</small></th><th className="is-num">Props</th><th>Notes</th>
    </tr></thead>
    <tbody>{rows.map(row => <tr key={row.gameId} className={`is-${row.state}`} onClick={event => open(event, row.gameId)}>
      <td className="nfl-slate-table__kickoff"><Kickoff row={row} /></td>
      <td className="nfl-slate-table__game"><Game row={row} /></td>
      <td className="nfl-slate-table__spread"><Value cell={row.spread} /></td>
      <td className="nfl-slate-table__total" data-label="o/u"><Value cell={row.total} /></td>
      <td className="nfl-slate-table__moneyline" data-label="ML"><Value cell={row.moneyline} /></td>
      <td className="nfl-slate-table__model is-muted" data-label="model">
        {row.model === null ? 'Unavailable' : <>{row.model.spread}<span className="nfl-slate-table__model-total"> · {row.model.total}</span></>}
      </td>
      <td className="nfl-slate-table__props is-num">{row.props}<span className="nfl-slate-table__unit"> props</span></td>
      <td className="nfl-slate-table__notes"><Notes row={row} /></td>
    </tr>)}</tbody>
  </table>
}
