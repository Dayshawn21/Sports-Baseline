import { Link } from 'react-router-dom'
import { MiniBars } from '~/components/shared/MiniBars'
import '~/components/shared/prop-table.css'
import { useNflLineOnlyProps } from '~/hooks/useNfl'
import { marketLabel } from '~/utils/nflLabels'
import { lineOnlyBars, lineOnlyGroups, mainRung, type NflLineOnlyRow } from '~/utils/nflLineOnly'
import type { NflPositionFilter } from '~/utils/nflPositions'
import './nfl-prop-table.css'

function rungLabel(line: number, oddsType: string | null): string {
  return oddsType && oddsType !== 'standard' ? `${line} ${oddsType}` : `${line}`
}

function Row({ row, market }: { row: NflLineOnlyRow, market: string }) {
  const main = mainRung(row)
  const others = row.rungs.filter(rung => rung !== main)
  // Oldest to newest, the same order as the bars beside it.
  const values = [...row.recent].reverse().map(game => game.value ?? '--').join(' · ')
  return <tr>
    <td className="prop-table__player">
      <Link className="prop-table__open" to={`/nfl/player/${row.playerId}`}>{row.playerName}</Link>
      <small>{row.position ?? '--'} · {marketLabel(market)}</small>
    </td>
    <td className="is-num" data-label="line">{main.line}<small>{main.oddsType ?? ''}</small></td>
    <td className="nfl-line-only-table__also" data-label="also">{others.length ? others.map(rung => rungLabel(rung.line, rung.oddsType)).join(' · ') : '--'}</td>
    <td title={values ? `Last games, oldest to newest: ${values}` : undefined}>
      <MiniBars bars={lineOnlyBars(row)} empty="No earlier games" title={bar => `${bar.value} vs ${bar.opponentTeam ?? '--'}`} />
    </td>
    <td className="prop-table__end is-num">{row.count ? `over ${row.overCount} of ${row.count}` : '--'}</td>
  </tr>
}

/** Item 35: stored line-only markets with recent results. Display only: no projection, edge, rank, drawer or signal color. */
export function NflLineOnlyProps({ gameId, position }: { gameId: number, position: NflPositionFilter }) {
  const query = useNflLineOnlyProps(gameId)
  const groups = query.data ? lineOnlyGroups(query.data.lines, position) : []
  if (query.isSuccess && groups.length === 0) return null
  return <section className="nfl-line-only" aria-label="Other lines">
    <h3 className="nfl-game-label">Other lines <small>not modelled · recent results only</small></h3>
    {query.isLoading && <p className="nfl-line-only__status">Loading other lines...</p>}
    {query.isError && <p className="nfl-line-only__status">Other lines could not load.</p>}
    {groups.map(group => <div key={group.market} className="nfl-line-only__market prop-table-panel">
      <h4>{marketLabel(group.market)}</h4>
      <table className="prop-table nfl-line-only-table" aria-label={`${marketLabel(group.market)} lines`}>
        <colgroup><col className="is-player" /><col className="is-line" /><col className="is-also" /><col className="is-bars" /><col className="is-over" /></colgroup>
        <thead><tr><th>Player</th><th className="is-num">Line</th><th>Also</th><th>Last 5</th><th className="is-num">Record</th></tr></thead>
        <tbody>{group.rows.map(row => <Row key={row.playerId} row={row} market={group.market} />)}</tbody>
      </table>
    </div>)}
  </section>
}
