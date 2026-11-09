import type { MouseEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import type { NhlSlateRowCell, NhlSlateRowModel } from '~/utils/nhlSlate'
import '~/components/nfl/nfl-slate-card.css'
import '~/components/nfl/nfl-slate-table.css'

function Value({ cell }: { cell: NhlSlateRowCell }) {
  return <>{cell.value}{cell.detail !== null && <small>{cell.detail}</small>}</>
}

function Game({ row }: { row: NhlSlateRowModel }) {
  const { away, home } = row
  const names = `${away.name} · ${home.name}`
  return <Link to={`/nhl/game/${row.gameId}`} aria-label={`${away.code} at ${home.code}, open game page`}>
    {away.score !== null && home.score !== null
      ? `${away.code} ${away.score} · ${home.code} ${home.score}`
      : `${away.code} @ ${home.code}`}
    <small title={names}>{names}</small>
  </Link>
}

const COLUMNS = ['kickoff', 'game', 'spread', 'total', 'moneyline', 'win', 'props', 'notes']

/** One date's games, one row each; a row opens its game page. Display only, every tag gray. */
export function NhlSlateTable({ rows }: { rows: NhlSlateRowModel[] }) {
  const navigate = useNavigate()
  const open = (event: MouseEvent, gameId: number) => {
    // The Game link handles its own clicks, so a click on it never navigates twice.
    if (event.target instanceof Element && event.target.closest('a')) return
    navigate(`/nhl/game/${gameId}`)
  }
  return <table className="nfl-slate-table nhl-slate-table" aria-label="Games">
    <colgroup>{COLUMNS.map(column => <col key={column} className={`is-${column}`} />)}</colgroup>
    <thead><tr>
      <th>Puck drop</th><th>Game</th><th>Puck line</th><th>Total</th><th>Moneyline</th>
      <th>Win <small>market</small></th><th className="is-num">Props</th><th>Notes</th>
    </tr></thead>
    <tbody>{rows.map(row => <tr key={row.gameId} className={`is-${row.state}`} onClick={event => open(event, row.gameId)}>
      <td className="nfl-slate-table__kickoff">{row.puckDrop}<small>{row.stateLabel}</small></td>
      <td className="nfl-slate-table__game"><Game row={row} /></td>
      <td className="nfl-slate-table__spread"><Value cell={row.puckLine} /></td>
      <td className="nfl-slate-table__total" data-label="o/u"><Value cell={row.total} /></td>
      <td className="nfl-slate-table__moneyline" data-label="ML"><Value cell={row.moneyline} /></td>
      <td className="nhl-slate-table__win is-muted" data-label="win">{row.win ?? '--'}</td>
      <td className="nfl-slate-table__props is-num">{row.props}<span className="nfl-slate-table__unit"> props</span></td>
      <td className="nfl-slate-table__notes"><span className="nfl-slate-table__tags">
        {row.tags.map(tag => <span key={tag} className="nfl-slate-card__tag">{tag}</span>)}
      </span></td>
    </tr>)}</tbody>
  </table>
}
