import { NflLineOnlyTable } from '~/components/nfl/NflLineOnlyProps'
import { useNflWeekLineOnlyProps } from '~/hooks/useNfl'
import { marketLabel } from '~/utils/nflLabels'
import { playerLineOnlyGroups } from '~/utils/nflPlayer'

/** Stored lines with no model: recent results only, no projection, edge, rank or color. Renders nothing when the player has none. */
export function NflPlayerOtherMarkets({ season, week, playerId }: { season: number, week: number, playerId: number }) {
  const board = useNflWeekLineOnlyProps(season, week)
  const groups = playerLineOnlyGroups(board.data?.games.flatMap(game => game.lines) ?? [], playerId)
  if (!board.isLoading && !board.isError && groups.length === 0) return null
  return <section aria-label="Other markets">
    <h2 className="nfl-player-section-title">Other markets <small>Recent results only, no model comparison</small></h2>
    {board.isLoading && <p className="nfl-player-note">Loading other markets...</p>}
    {board.isError && <p className="nfl-player-note">Other markets could not be loaded.</p>}
    {groups.map(group => <div key={group.market} className="nfl-player-card nfl-player-other">
      <div className="nfl-player-card__head"><h3 className="nfl-player-prop__title">{marketLabel(group.market)}</h3></div>
      <NflLineOnlyTable group={group} />
    </div>)}
  </section>
}
