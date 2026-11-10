import type { MouseEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { SlateMatchupTeams } from '~/components/shared/SlateMatchupTeams'
import { SlatePropsCell } from '~/components/shared/SlatePropsCell'
import type { NhlSlateRowCell, NhlSlateRowModel } from '~/utils/nhlSlate'
import { splitTags } from '~/utils/slatePeriod'
import '~/components/nfl/nfl-slate-card.css'
import '~/components/nfl/nfl-slate-table.css'

function Value({ cell }: { cell: NhlSlateRowCell }) {
  return <>{cell.value}{cell.detail !== null && <small>{cell.detail}</small>}</>
}

function Game({ row }: { row: NhlSlateRowModel }) {
  const { away, home } = row
  return <Link to={`/nhl/game/${row.gameId}`} aria-label={`${away.code} at ${home.code}, open game page`}>
    <SlateMatchupTeams sport="nhl" away={away} home={home} />
  </Link>
}

// The two goalie tags come first; the rest fold into "+N" so the notes stay one line.
const SHOWN_TAGS = 2

function Notes({ tags }: { tags: string[] }) {
  const { hidden } = splitTags(tags, SHOWN_TAGS)
  return <span className="nfl-slate-table__tags">
    {tags.map((tag, index) => <span key={tag} className={`nfl-slate-card__tag${index >= SHOWN_TAGS ? ' is-overflow' : ''}`} title={tag}>{tag}</span>)}
    {hidden.length > 0 && <span className="nfl-slate-card__tag is-more" title={hidden.join(', ')} aria-hidden="true">+{hidden.length}</span>}
  </span>
}

function PuckDrop({ row }: { row: NhlSlateRowModel }) {
  // "Scheduled" under every upcoming time says nothing; a phone shows the state in place of the time.
  return <><span className="nhl-slate-table__time">{row.puckDrop}</span>{row.state !== 'upcoming' && <small>{row.stateLabel}</small>}</>
}

const COLUMNS = ['kickoff', 'game', 'spread', 'total', 'moneyline', 'win', 'props', 'notes']

/** One date's games, one row each; a row opens its game page. Display only, every tag gray. */
export function NhlSlateTable({ rows, label = 'Games', staleOdds = false }: { rows: NhlSlateRowModel[], label?: string, staleOdds?: boolean }) {
  const navigate = useNavigate()
  const open = (event: MouseEvent, gameId: number) => {
    // The Game link handles its own clicks, so a click on it never navigates twice.
    if (event.target instanceof Element && event.target.closest('a')) return
    navigate(`/nhl/game/${gameId}`)
  }
  return <table className={`nfl-slate-table nhl-slate-table${staleOdds ? ' has-stale-odds' : ''}`} aria-label={label}>
    <colgroup>{COLUMNS.map(column => <col key={column} className={`is-${column}`} />)}</colgroup>
    <thead><tr>
      <th>Puck drop</th><th>Game</th><th>Puck line</th><th>Total</th><th>Moneyline</th>
      <th>Win <small>market</small></th><th className="is-num">Props</th><th>Notes</th>
    </tr></thead>
    <tbody>{rows.map(row => <tr key={row.gameId} className={`is-${row.state}`} onClick={event => open(event, row.gameId)}>
      <td className="nfl-slate-table__kickoff"><PuckDrop row={row} /></td>
      <td className="nfl-slate-table__game"><Game row={row} /></td>
      <td className="nfl-slate-table__spread"><Value cell={row.puckLine} />{row.oddsAge !== null && <small className="nfl-slate-table__age">{row.oddsAge}</small>}</td>
      <td className="nfl-slate-table__total" data-label="o/u"><Value cell={row.total} /></td>
      <td className="nfl-slate-table__moneyline" data-label="ML"><Value cell={row.moneyline} /></td>
      <td className="nhl-slate-table__win is-muted" data-label="win">{row.win ?? '--'}</td>
      <SlatePropsCell count={row.props} />
      <td className="nfl-slate-table__notes"><Notes tags={row.tags} /></td>
    </tr>)}</tbody>
  </table>
}
