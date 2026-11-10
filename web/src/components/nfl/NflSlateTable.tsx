import type { MouseEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { SlateMatchupTeams } from '~/components/shared/SlateMatchupTeams'
import { SlatePropsCell } from '~/components/shared/SlatePropsCell'
import type { NflSlateRowCell, NflSlateRowModel } from '~/utils/nflSlate'
import './nfl-slate-card.css'
import './nfl-slate-table.css'

function Value({ cell }: { cell: NflSlateRowCell }) {
  return <>{cell.value}{cell.detail !== null && <small>{cell.detail}</small>}</>
}

function Game({ row }: { row: NflSlateRowModel }) {
  const { away, home } = row
  return <Link to={`/nfl/game/${row.gameId}`} aria-label={`${away.code} at ${home.code}, open game page`}>
    <SlateMatchupTeams sport="nfl" away={away} home={home} />
    <small>{away.record} · {home.record}</small>
  </Link>
}

function Notes({ row }: { row: NflSlateRowModel }) {
  const { injuries } = row
  return <span className="nfl-slate-table__tags">
    {injuries !== null && injuries.out > 0 && <span className="nfl-slate-card__tag is-out">{injuries.out} Out</span>}
    {injuries !== null && injuries.doubtful > 0 && <span className="nfl-slate-card__tag is-caution" title={`${injuries.doubtful} doubtful`} aria-label={`${injuries.doubtful} doubtful`}>{injuries.doubtful} D</span>}
    {injuries !== null && injuries.questionable > 0 && <span className="nfl-slate-card__tag is-caution" title={`${injuries.questionable} questionable`} aria-label={`${injuries.questionable} questionable`}>{injuries.questionable} Q</span>}
    {row.qbChange.map(team => <span key={`qb-${team}`} className="nfl-slate-card__tag is-caution">QB change: {team}</span>)}
    {row.shortWeek.map(team => <span key={team} className="nfl-slate-card__tag">Short week: {team}</span>)}
    {row.state !== 'final' && row.state !== 'pending' && row.conditions !== null && <span className="nfl-slate-table__conditions">{row.conditions}</span>}
  </span>
}

function Kickoff({ row }: { row: NflSlateRowModel }) {
  if (row.state === 'pending') return <><span className="nfl-slate-table__time">{row.kickoff}</span><small className="nfl-slate-table__result">Result pending</small></>
  if (row.state !== 'live') return <>{row.kickoff}</>
  return <><span className="nfl-slate-card__live">Live</span>{row.scorePending
    ? <small className="nfl-slate-table__pending">score pending</small>
    : <small>{row.kickoff}</small>}</>
}

function Spread({ row }: { row: NflSlateRowModel }) {
  return <><Value cell={row.spread} />{row.oddsAge !== null && <small className="nfl-slate-table__age">{row.oddsAge}</small>}</>
}

const COLUMNS = ['kickoff', 'game', 'spread', 'total', 'moneyline', 'model', 'props', 'notes']

/** A kickoff window inside the one slate table; a null title draws no group row (the finals disclosure has its own). */
export interface NflSlateRowGroup {
  key: string
  title: string | null
  note?: string
  rows: NflSlateRowModel[]
}

/** The week's games in one table under one header, a group row per kickoff window; a row opens its game page. Display only, never green. */
export function NflSlateTable({ groups, label, staleOdds = false }: { groups: NflSlateRowGroup[], label: string, staleOdds?: boolean }) {
  const navigate = useNavigate()
  const open = (event: MouseEvent, gameId: number) => {
    // The Game link handles its own clicks, so a click on it never navigates twice.
    if (event.target instanceof Element && event.target.closest('a')) return
    navigate(`/nfl/game/${gameId}`)
  }
  return <table className={`nfl-slate-table${staleOdds ? ' has-stale-odds' : ''}`} aria-label={label}>
    <colgroup>{COLUMNS.map(column => <col key={column} className={`is-${column}`} />)}</colgroup>
    <thead><tr>
      <th>Kickoff</th><th>Game</th><th>Spread</th><th>Total</th><th>Moneyline</th>
      <th>Model <small>not a pick</small></th><th className="is-num">Props</th><th>Notes</th>
    </tr></thead>
    {groups.map(group => <tbody key={group.key}>
      {group.title !== null && <tr className="nfl-slate-table__group">
        <th colSpan={COLUMNS.length} scope="colgroup">{group.title}{group.note && <small>{group.note}</small>}</th>
      </tr>}
      {group.rows.map(row => <tr key={row.gameId} className={`is-${row.state}`} onClick={event => open(event, row.gameId)}>
        <td className="nfl-slate-table__kickoff"><Kickoff row={row} /></td>
        <td className="nfl-slate-table__game"><Game row={row} /></td>
        <td className="nfl-slate-table__spread"><Spread row={row} /></td>
        <td className="nfl-slate-table__total" data-label="o/u"><Value cell={row.total} /></td>
        <td className="nfl-slate-table__moneyline" data-label="ML"><Value cell={row.moneyline} /></td>
        <td className="nfl-slate-table__model is-muted" data-label="model">
          {row.model === null ? 'Unavailable' : <>{row.model.spread}<span className="nfl-slate-table__model-total"> · {row.model.total}</span></>}
        </td>
        <SlatePropsCell count={row.props} />
        <td className="nfl-slate-table__notes"><Notes row={row} /></td>
      </tr>)}
    </tbody>)}
  </table>
}
