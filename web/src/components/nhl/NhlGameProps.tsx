import { Link } from 'react-router-dom'
import ErrorState from '~/components/shared/ErrorState'
import LoadingState from '~/components/shared/LoadingState'
import { useNhlLineOnlyProps } from '~/hooks/useNhl'
import { nhlTimeLabel } from '~/utils/nhlGame'
import { nhlOddsTypeCounts, nhlPropListGroups, type NhlPropListGroup, type NhlPropListRow } from '~/utils/nhlLineOnly'
import { nhlPlayerPath } from '~/utils/nhlPlayer'
import {
  NHL_PROBABILITY_CAPTION, NHL_PROJECTION_CAPTION, nhlGapLabel, nhlPercentLabel, nhlProbabilityNote, nhlProjectionNote, nhlProjectionValue,
} from '~/utils/nhlProjection'

function alternates(row: NhlPropListRow): string {
  return row.rungs
    .filter(rung => rung.oddsType !== 'standard')
    .map(rung => `${rung.oddsTypeLabel} ${rung.label}${rung.gap === null ? '' : ` (${nhlGapLabel(rung.gap)})`}`)
    .join(' / ')
}

function MarketTable({ group, gameDate }: { group: NhlPropListGroup, gameDate: string }) {
  const covers = group.rows.some(row => row.coversProbability)
  const weakNote = nhlProbabilityNote(group.market)
  return <section className="nhl-prop-group" aria-labelledby={`nhl-props-${group.market}`}>
    <h3 id={`nhl-props-${group.market}`}>{group.label} <small>{group.rows.length} {group.rows.length === 1 ? 'player' : 'players'}</small></h3>
    {covers && <p className="nhl-prop-caption">{NHL_PROBABILITY_CAPTION}. Shown for the standard line only.{weakNote && ` ${weakNote}`}</p>}
    <table className="nhl-prop-table" aria-label={`${group.label} lines`}>
      <thead><tr><th scope="col">Player</th><th scope="col">Standard</th><th scope="col">Proj</th><th scope="col">Gap</th>{covers && <th scope="col">P(over)</th>}<th scope="col">Other lines</th><th scope="col" className="nhl-prop-updated">Updated (CT)</th></tr></thead>
      <tbody>{group.rows.map(row => <tr key={row.key}>
        <td>
          <strong><Link className="nhl-prop-link" to={nhlPlayerPath(row.playerId, { date: gameDate, market: row.market })}>{row.playerName}</Link></strong>
          <small>{row.team ?? '--'}{row.position ? ` / ${row.position}` : ''}</small>
          <time className="nhl-prop-updated-mobile" dateTime={row.fetchedAt}>{nhlTimeLabel(row.fetchedAt, true)}</time>
        </td>
        <td className="nhl-prop-line">{row.standard ?? '--'}</td>
        <td className="nhl-prop-line">{nhlProjectionValue(row.projection)}{nhlProjectionNote(row.projection) && <small>{nhlProjectionNote(row.projection)}</small>}</td>
        <td className="nhl-prop-line">{nhlGapLabel(row.standardGap)}</td>
        {covers && <td className="nhl-prop-line">{nhlPercentLabel(row.standardPOver)}{row.standardProbabilityNote && <small>{row.standardProbabilityNote}</small>}</td>}
        <td>{alternates(row) || '--'}</td>
        <td className="nhl-prop-updated"><time dateTime={row.fetchedAt}>{nhlTimeLabel(row.fetchedAt, true)}</time></td>
      </tr>)}</tbody>
    </table>
  </section>
}

/** The game page's player props: one row per player per market, each opening that player's page on this game's date. */
export function NhlGameProps({ gameId, gameDate }: { gameId: number, gameDate: string }) {
  const query = useNhlLineOnlyProps(gameId)
  if (query.isLoading) return <LoadingState message="Loading NHL player props..." />
  if (query.isError || !query.data) return <ErrorState error={query.error} onRetry={() => void query.refetch()} />
  const lines = query.data.lines
  const groups = nhlPropListGroups(lines)
  return <section className="nhl-props" aria-label="Player props">
    <div className="nhl-props-heading"><h2>Player props</h2><p>PrizePicks full-game lines. {NHL_PROJECTION_CAPTION}. Open a player for the form chart and every line.</p></div>
    <dl className="nhl-props-counts" aria-label="Stored prop line counts">
      <div><dt>Total lines</dt><dd>{lines.length}</dd></div>
      {nhlOddsTypeCounts(lines).map(entry => <div key={entry.oddsType}><dt>{entry.label}</dt><dd>{entry.count}</dd></div>)}
    </dl>
    {groups.length === 0
      ? <p className="nfl-game-empty">No linked full-game PrizePicks lines are stored for this game.</p>
      : groups.map(group => <MarketTable key={group.market} group={group} gameDate={gameDate} />)}
  </section>
}
