import { NbaLineOnlyProps } from '~/components/nba/NbaLineOnlyProps'
import { NbaProps } from '~/components/nba/NbaProps'
import GamePropFilters from '~/components/shared/GamePropFilters'
import { useGamePropFilters } from '~/hooks/useGamePropFilters'
import { useNbaLineOnlyProps, useNbaProps } from '~/hooks/useNba'
import type { NbaGameDetail } from '~/types/nba'
import { gamePlayerOptions } from '~/utils/propFilters'

/** The game page's Props tab: one set of filters over the modelled and other-line tables. */
export function NbaGameProps({ game }: { game: NbaGameDetail }) {
  const { filter, onPlayers, onTeam } = useGamePropFilters(game)
  const props = useNbaProps(game.gameId)
  const other = useNbaLineOnlyProps(game.gameId)
  const playerNames = gamePlayerOptions([...(props.data?.lines ?? []), ...(other.data?.lines ?? [])], game, filter)
  return <div className="nfl-game-main">
    <GamePropFilters game={game} playerNames={playerNames} filter={filter} onPlayers={onPlayers} onTeam={onTeam} />
    <NbaProps key={`props:${game.gameId}`} game={game} gameDate={game.gameDate} filter={filter} />
    <NbaLineOnlyProps key={`other:${game.gameId}`} game={game} gameId={game.gameId} startUtc={game.startUtc} gameDate={game.gameDate} filter={filter} />
  </div>
}
