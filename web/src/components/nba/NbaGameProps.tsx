import { NbaLineOnlyProps } from '~/components/nba/NbaLineOnlyProps'
import { NbaProps } from '~/components/nba/NbaProps'
import GamePropFilters from '~/components/shared/GamePropFilters'
import { useGamePropFilters } from '~/hooks/useGamePropFilters'
import type { NbaGameDetail } from '~/types/nba'

/** The game page's Props tab: one set of filters over the modelled and other-line tables. */
export function NbaGameProps({ game }: { game: NbaGameDetail }) {
  const { filter, onQuery, onTeam } = useGamePropFilters(game)
  return <div className="nfl-game-main">
    <GamePropFilters game={game} filter={filter} onQuery={onQuery} onTeam={onTeam} />
    <NbaProps key={`props:${game.gameId}`} game={game} gameDate={game.gameDate} filter={filter} />
    <NbaLineOnlyProps key={`other:${game.gameId}`} game={game} gameId={game.gameId} startUtc={game.startUtc} gameDate={game.gameDate} filter={filter} />
  </div>
}
