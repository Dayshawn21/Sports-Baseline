import { NbaPropTable } from '~/components/nba/NbaPropTable'
import { NbaSlateDigest } from '~/components/nba/NbaSlateDigest'
import { useNbaProps } from '~/hooks/useNba'
import { nbaMarketLabel } from '~/utils/nbaLineOnly'
import { nbaPlayerPath } from '~/utils/nbaPlayer'
import { nbaPropGroups } from '~/utils/nbaProps'
import { UNAVAILABLE_NBA_INJURIES } from '~/utils/nbaInjuries'
import { nbaGameGaps, nbaSlateDigest, type NbaGapGame } from '~/utils/nbaSlate'
import { gamePropRowMatches, type GamePropFilter } from '~/utils/propFilters'

/** Modelled PrizePicks lines with the reference projection (20g2). Gray: no pick, rank or signal color until 20g4. A row or digest box opens the player page on this game's date. */
export function NbaProps({ game, gameDate, filter }: { game: NbaGapGame, gameDate: string, filter: GamePropFilter }) {
  const { gameId, startUtc } = game
  const query = useNbaProps(gameId)
  const groups = query.data ? nbaPropGroups(query.data.lines) : []
  const shown = groups.map(group => ({ ...group, cards: group.cards.filter(card => gamePropRowMatches(card, game, filter)) })).filter(group => group.cards.length > 0)
  const injuryReport = query.data?.injuryReport ?? UNAVAILABLE_NBA_INJURIES
  const now = new Date()
  const digest = query.data ? nbaSlateDigest(nbaGameGaps(game, query.data.lines, now)) : []
  if (query.isSuccess && groups.length === 0) return null
  return <section className="nfl-line-only nba-props" aria-label="Props">
    <NbaSlateDigest items={digest} scope="this game" playerPath={item => nbaPlayerPath(item.playerId, { date: gameDate, market: item.marketKey })} />
    <h3 className="nfl-game-label">Props <small>reference projection · gray until the ranking check adopts a slice</small></h3>
    {query.isLoading && <p className="nfl-line-only__status">Loading props...</p>}
    {query.isError && <p className="nfl-line-only__status">Props could not load.</p>}
    {groups.length > 0 && shown.length === 0 && <p className="nfl-line-only__status">No props match these filters.</p>}
    {shown.map(group => <div key={group.market} className="nfl-line-only__market prop-table-panel">
      <h4>{nbaMarketLabel(group.market)}</h4>
      <NbaPropTable market={group.market} cards={group.cards}
        pathFor={playerId => nbaPlayerPath(playerId, { date: gameDate, market: group.market })}
        injuryReport={injuryReport} startUtc={startUtc} now={now} />
    </div>)}
  </section>
}
