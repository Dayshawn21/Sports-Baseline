import { Link } from 'react-router-dom'
import { nflPlayerMarketLink } from '~/utils/nflPlayer'
import { MiniBars } from '~/components/shared/MiniBars'
import '~/components/shared/prop-table.css'
import { useNflLineOnlyProps } from '~/hooks/useNfl'
import { marketLabel } from '~/utils/nflLabels'
import { lineOnlyBars, lineOnlyGroups, mainRung, type NflLineOnlyGroup, type NflLineOnlyRow } from '~/utils/nflLineOnly'
import type { NflPositionFilter } from '~/utils/nflPositions'
import './nfl-prop-table.css'

function rungLabel(line: number, oddsType: string | null): string {
  return oddsType && oddsType !== 'standard' ? `${line} ${oddsType}` : `${line}`
}

function Row({ row, market }: { row: NflLineOnlyRow, market: string }) {
  const main = mainRung(row)
  const others = row.rungs.filter(rung => rung !== main)
  return <tr>
    <td className="prop-table__player">
      <Link className="prop-table__open" to={nflPlayerMarketLink(row.playerId, market)}>{row.playerName}</Link>
      <small>{row.position ?? '--'} · {marketLabel(market)}</small>
    </td>
    <td className="is-num" data-label="line">{main.line}<small>{main.oddsType ?? ''}</small></td>
    <td className="nfl-line-only-table__also" data-label="also">{others.length ? others.map(rung => rungLabel(rung.line, rung.oddsType)).join(' · ') : '--'}</td>
    <td>
      <MiniBars interactive bars={lineOnlyBars(row)} empty="No earlier games" title={bar => `${bar.value} vs ${bar.opponentTeam ?? '--'}`} />
    </td>
    <td className="prop-table__end is-num">{row.count ? `over ${row.overCount} of ${row.count}` : '--'}</td>
  </tr>
}

export function NflLineOnlyTable({ group }: { group: NflLineOnlyGroup }) {
  return <table className="prop-table nfl-line-only-table" aria-label={`${marketLabel(group.market)} lines`}>
    <colgroup><col className="is-player" /><col className="is-line" /><col className="is-also" /><col className="is-bars" /><col className="is-over" /></colgroup>
    <thead><tr><th>Player</th><th className="is-num">Line</th><th>Also</th><th>Last 5</th><th className="is-num">Record</th></tr></thead>
    <tbody>{group.rows.map(row => <Row key={row.playerId} row={row} market={group.market} />)}</tbody>
  </table>
}

/** Item 35: stored line-only markets with recent results. Display only: no projection, edge, rank, drawer or signal color. */
export function NflLineOnlyProps({ gameId, position }: { gameId: number, position: NflPositionFilter }) {
  const query = useNflLineOnlyProps(gameId)
  const groups = query.data ? lineOnlyGroups(query.data.lines, position) : []
  if (query.isSuccess && groups.length === 0) return null
  return <details className="nfl-line-only" aria-label="Other markets">
    <summary><span>Other markets{query.isSuccess ? ` · ${groups.length}` : ''}</span><small>Recent results only · no model comparison</small></summary>
    <div className="nfl-line-only__body">
    {query.isLoading && <p className="nfl-line-only__status">Loading other lines...</p>}
    {query.isError && <p className="nfl-line-only__status">Other lines could not load.</p>}
    {groups.map(group => <div key={group.market} className="nfl-line-only__market prop-table-panel">
      <h4>{marketLabel(group.market)}</h4>
      <NflLineOnlyTable group={group} />
    </div>)}
    </div>
  </details>
}
