import ErrorState from '~/components/shared/ErrorState'
import LoadingState from '~/components/shared/LoadingState'
import { useNhlLineOnlyProps } from '~/hooks/useNhl'
import { nhlTimeLabel } from '~/utils/nhlGame'
import { nhlLineOnlyGroups, nhlOddsTypeCounts, type NhlLineOnlyGroup } from '~/utils/nhlLineOnly'

function MarketTable({ group }: { group: NhlLineOnlyGroup }) {
  return <section className="nhl-prop-group" aria-labelledby={`nhl-props-${group.market}`}>
    <h3 id={`nhl-props-${group.market}`}>{group.label} <small>{group.rows.length} lines</small></h3>
    <table className="nhl-prop-table" aria-label={`${group.label} lines`}>
      <thead><tr><th scope="col">Player</th><th scope="col">Line</th><th scope="col">Offering</th><th scope="col" className="nhl-prop-updated">Updated (CT)</th></tr></thead>
      <tbody>{group.rows.map(row => <tr key={row.key}>
        <td><strong>{row.playerName}</strong><small>{row.team ?? '--'}{row.position ? ` / ${row.position}` : ''}</small>
          <time className="nhl-prop-updated-mobile" dateTime={row.fetchedAt}>{nhlTimeLabel(row.fetchedAt, true)}</time>
        </td>
        <td className="nhl-prop-line">{row.lineLabel}</td>
        <td>{row.oddsTypeLabel}</td>
        <td className="nhl-prop-updated"><time dateTime={row.fetchedAt}>{nhlTimeLabel(row.fetchedAt, true)}</time></td>
      </tr>)}</tbody>
    </table>
  </section>
}

export function NhlLineOnlyProps({ gameId }: { gameId: number }) {
  const query = useNhlLineOnlyProps(gameId)
  if (query.isLoading) return <LoadingState message="Loading NHL player props..." />
  if (query.isError || !query.data) return <ErrorState error={query.error} onRetry={() => void query.refetch()} />
  const lines = query.data.lines
  const groups = nhlLineOnlyGroups(lines)
  return <section className="nhl-props" aria-label="Player props">
    <div className="nhl-props-heading"><h2>Player props</h2><p>PrizePicks full-game lines. Not modelled.</p></div>
    <dl className="nhl-props-counts" aria-label="Stored prop line counts">
      <div><dt>Total lines</dt><dd>{lines.length}</dd></div>
      {nhlOddsTypeCounts(lines).map(entry => <div key={entry.oddsType}><dt>{entry.label}</dt><dd>{entry.count}</dd></div>)}
    </dl>
    {groups.length === 0
      ? <p className="nfl-game-empty">No linked full-game PrizePicks lines are stored for this game.</p>
      : groups.map(group => <MarketTable key={group.market} group={group} />)}
  </section>
}
