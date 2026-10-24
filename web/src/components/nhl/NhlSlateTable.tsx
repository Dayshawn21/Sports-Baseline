import type { MouseEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { nhlBookLabel, nhlTimeLabel, type NhlMarketCell } from '~/utils/nhlGame'
import type { nhlSlateRow } from '~/utils/nhlSlate'

type SlateRow = ReturnType<typeof nhlSlateRow>

function Market({ cell }: { cell: NhlMarketCell }) {
  return <><span>{cell.value}</span><small>{cell.detail}</small>
    {cell.book !== null && <small className="nhl-slate-source">{nhlBookLabel(cell.book)}
      {cell.fetchedAt !== null && <time dateTime={cell.fetchedAt}>{nhlTimeLabel(cell.fetchedAt, true)}</time>}
    </small>}
  </>
}

export function NhlSlateTable({ rows }: { rows: SlateRow[] }) {
  const navigate = useNavigate()
  const open = (event: MouseEvent, gameId: number) => {
    if (event.target instanceof Element && event.target.closest('a')) return
    navigate(`/nhl/game/${gameId}`)
  }
  return <table className="nhl-slate-table" aria-label="Games">
    <thead><tr><th scope="col">Puck drop (CT)</th><th scope="col">Game</th><th scope="col">Puck line</th>
      <th scope="col">Total</th><th scope="col">Moneyline</th><th scope="col">Win probability <small>market</small></th><th scope="col">Props</th></tr></thead>
    <tbody>{rows.map(row => <tr key={row.gameId} onClick={event => open(event, row.gameId)}>
      <td className="nhl-slate-when">{row.puckDrop}<small>{row.stateLabel}</small></td>
      <td className="nhl-slate-game"><Link to={`/nhl/game/${row.gameId}`} aria-label={`${row.away.code} at ${row.home.code}, open game page`}>
        {row.away.score !== null && row.home.score !== null
          ? `${row.away.code} ${row.away.score} / ${row.home.code} ${row.home.score}`
          : `${row.away.code} @ ${row.home.code}`}
      </Link><small>{row.away.name}<br />{row.home.name}</small></td>
      <td data-label="Puck line"><Market cell={row.puckLine} /></td>
      <td data-label="Total"><Market cell={row.total} /></td>
      <td data-label="Moneyline"><Market cell={row.moneyline} /></td>
      <td data-label="Market win probability"><Market cell={row.probability} /></td>
      <td className="nhl-slate-props" data-label="Props">{row.props}</td>
    </tr>)}</tbody>
  </table>
}
