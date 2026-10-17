import type { MouseEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import type { NbaSlateRowCell, NbaSlateRowModel } from '~/utils/nbaSlate'
import '~/components/nfl/nfl-slate-card.css'
import '~/components/nfl/nfl-slate-table.css'
import './nba-slate-table.css'

function Value({ cell }: { cell: NbaSlateRowCell }) {
  return <>{cell.value}{cell.detail !== null && <small>{cell.detail}</small>}</>
}

function Game({ row }: { row: NbaSlateRowModel }) {
  const { away, home } = row
  const scored = away.score !== null && home.score !== null
  return <Link to={`/nba/game/${row.gameId}`} aria-label={`${away.code} at ${home.code}, open game page`}>
    {scored
      ? <><span className={away.lost ? 'is-loser' : ''}>{away.code} {away.score}</span> · <span className={home.lost ? 'is-loser' : ''}>{home.code} {home.score}</span></>
      : `${away.code} @ ${home.code}`}
    <small>{away.record} · {home.record}</small>
  </Link>
}

const COLUMNS = ['kickoff', 'game', 'spread', 'total', 'moneyline', 'win', 'props', 'notes']

/** One date's games, one row each; a row opens its game page. Display only, never green. */
export function NbaSlateTable({ rows }: { rows: NbaSlateRowModel[] }) {
  const navigate = useNavigate()
  const open = (event: MouseEvent, gameId: number) => {
    // The Game link handles its own clicks, so a click on it never navigates twice.
    if (event.target instanceof Element && event.target.closest('a')) return
    navigate(`/nba/game/${gameId}`)
  }
  return <table className="nfl-slate-table nba-slate-table" aria-label="Games">
    <colgroup>{COLUMNS.map(column => <col key={column} className={`is-${column}`} />)}</colgroup>
    <thead><tr>
      <th>Tip</th><th>Game</th><th>Spread</th><th>Total</th><th>Moneyline</th>
      <th>Win <small>market</small></th><th className="is-num">Props</th><th>Notes</th>
    </tr></thead>
    <tbody>{rows.map(row => <tr key={row.gameId} className={`is-${row.state}`} onClick={event => open(event, row.gameId)}>
      <td className="nfl-slate-table__kickoff">{row.tip}</td>
      <td className="nfl-slate-table__game"><Game row={row} /></td>
      <td className="nfl-slate-table__spread"><Value cell={row.spread} /></td>
      <td className="nfl-slate-table__total" data-label="o/u"><Value cell={row.total} /></td>
      <td className="nfl-slate-table__moneyline" data-label="ML"><Value cell={row.moneyline} /></td>
      <td className="nba-slate-table__win is-muted" data-label="win">{row.win ?? '--'}</td>
      <td className="nfl-slate-table__props is-num">{row.props}<span className="nfl-slate-table__unit"> props</span></td>
      <td className="nfl-slate-table__notes"><span className="nfl-slate-table__tags">
        {row.tags.map(tag => <span key={tag} className="nfl-slate-card__tag">{tag}</span>)}
        {row.note !== null && <span className="nfl-slate-table__conditions">{row.note}</span>}
      </span></td>
    </tr>)}</tbody>
  </table>
}
