import { Link } from 'react-router-dom'
import type { NflSeasonWeek } from '~/types/nfl'
import { nflPlayerMarketLink } from '~/utils/nflPlayer'
import { AltLinesChip } from '~/components/shared/AltLinesChip'
import { MiniBars } from '~/components/shared/MiniBars'
import { StatStrip } from '~/components/shared/StatStrip'
import '~/components/shared/prop-table.css'
import { useNflLineOnlyProps } from '~/hooks/useNfl'
import { marketLabel } from '~/utils/nflLabels'
import { lineOnlyBars, lineOnlyGroups, mainRung, type NflLineOnlyGroup, type NflLineOnlyRow } from '~/utils/nflLineOnly'
import type { NflPositionFilter } from '~/utils/nflPositions'
import { gamePropRowMatches, type GamePropFilter } from '~/utils/propFilters'
import { REFERENCE, groupAltLines, statStrip } from '~/utils/propRowVisuals'
import './nfl-prop-table.css'

function rungLabel(line: number, oddsType: string | null): string {
  return oddsType && oddsType !== 'standard' ? `${line} ${oddsType}` : `${line}`
}

function Row({ row, market, week }: { row: NflLineOnlyRow, market: string, week: NflSeasonWeek | null }) {
  const main = mainRung(row)
  const alts = groupAltLines(row.rungs)?.alts.map(rung => rungLabel(rung.line, rung.oddsType)) ?? []
  return <tr>
    <td className="prop-table__player">
      <Link className="prop-table__open" to={nflPlayerMarketLink(row.playerId, market, week)}>{row.playerName}</Link>
      <small>{row.position ?? '--'} · {marketLabel(market)}</small>
    </td>
    <td className="is-num" data-label="line">{main.line}<small>{main.oddsType ?? ''}</small></td>
    <td className="nfl-line-only-table__also" data-label="also">{alts.length ? <AltLinesChip labels={alts} context={marketLabel(market)} /> : '--'}</td>
    <td>
      <MiniBars interactive bars={lineOnlyBars(row)} empty="No earlier games" title={bar => `${bar.value} vs ${bar.opponentTeam ?? '--'}`} />
      <StatStrip cells={statStrip(row.recent.flatMap(game => game.value === null ? [] : [game.value]), main.line, REFERENCE)} />
    </td>
    <td className="prop-table__end is-num">{row.count ? `over ${row.overCount} of ${row.count}` : '--'}</td>
  </tr>
}

export function NflLineOnlyTable({ group, week = null }: { group: NflLineOnlyGroup, week?: NflSeasonWeek | null }) {
  return <table className="prop-table nfl-line-only-table" aria-label={`${marketLabel(group.market)} lines`}>
    <colgroup><col className="is-player" /><col className="is-line" /><col className="is-also" /><col className="is-bars" /><col className="is-over" /></colgroup>
    <thead><tr><th>Player</th><th className="is-num">Line</th><th>Also</th><th>Last 5</th><th className="is-num">Record</th></tr></thead>
    <tbody>{group.rows.map(row => <Row key={row.playerId} row={row} market={group.market} week={week} />)}</tbody>
  </table>
}

/** Item 35: stored line-only markets with recent results. Display only: no projection, edge, rank, drawer or signal color. */
export function NflLineOnlyProps({ game, position, week, filter }: {
  game: { gameId: number, awayTeam: string, homeTeam: string }, position: NflPositionFilter, week: NflSeasonWeek, filter: GamePropFilter,
}) {
  const query = useNflLineOnlyProps(game.gameId)
  const groups = query.data ? lineOnlyGroups(query.data.lines, position) : []
  const shown = groups.map(group => ({ ...group, rows: group.rows.filter(row => gamePropRowMatches(row, game, filter)) })).filter(group => group.rows.length > 0)
  if (query.isSuccess && groups.length === 0) return null
  return <details className="nfl-line-only" aria-label="Other markets">
    <summary><span>Other markets{query.isSuccess ? ` · ${shown.length}` : ''}</span><small>Recent results only · no model comparison</small></summary>
    <div className="nfl-line-only__body">
    {query.isLoading && <p className="nfl-line-only__status">Loading other lines...</p>}
    {query.isError && <p className="nfl-line-only__status">Other lines could not load.</p>}
    {groups.length > 0 && shown.length === 0 && <p className="nfl-line-only__status">No other markets match these filters.</p>}
    {shown.map(group => <div key={group.market} className="nfl-line-only__market prop-table-panel">
      <h4>{marketLabel(group.market)}</h4>
      <NflLineOnlyTable group={group} week={week} />
    </div>)}
    </div>
  </details>
}
