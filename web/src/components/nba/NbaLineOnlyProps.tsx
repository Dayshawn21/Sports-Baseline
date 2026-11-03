import { NbaLineOnlyTable } from '~/components/nba/NbaPropTable'
import { useNbaLineOnlyProps } from '~/hooks/useNba'
import { nbaLineOnlyGroups, nbaMarketLabel } from '~/utils/nbaLineOnly'
import { nbaPlayerPath } from '~/utils/nbaPlayer'
import { UNAVAILABLE_NBA_INJURIES } from '~/utils/nbaInjuries'

/** Stored PrizePicks lines with recent results. Display only: no projection, edge, rank or signal color until 20g. A row opens the player page on this game's date. */
export function NbaLineOnlyProps({ gameId, startUtc, gameDate }: { gameId: number, startUtc: string | null, gameDate: string }) {
  const query = useNbaLineOnlyProps(gameId)
  const groups = query.data ? nbaLineOnlyGroups(query.data.lines) : []
  const injuryReport = query.data?.injuryReport ?? UNAVAILABLE_NBA_INJURIES
  const now = new Date()
  if (query.isSuccess && groups.length === 0) return null
  return <section className="nfl-line-only" aria-label="Other lines">
    <h3 className="nfl-game-label">Other lines <small>not modelled · recent results only</small></h3>
    {query.isLoading && <p className="nfl-line-only__status">Loading lines...</p>}
    {query.isError && <p className="nfl-line-only__status">Lines could not load.</p>}
    {groups.map(group => <div key={group.market} className="nfl-line-only__market prop-table-panel">
      <h4>{nbaMarketLabel(group.market)}</h4>
      <NbaLineOnlyTable market={group.market} rows={group.rows}
        pathFor={playerId => nbaPlayerPath(playerId, { date: gameDate, market: group.market })}
        injuryReport={injuryReport} startUtc={startUtc} now={now} />
    </div>)}
  </section>
}
