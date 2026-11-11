import { useMemo } from 'react'
import { useSearchParams } from 'react-router-dom'
import {
  activeGameFilters, activeTeamFilter, gameTeams, parseGameFilters, parsePlayerFilter, parseTeamFilter, teamAfterGames, withPropListFilters, type BoardFilter, type PropListFilterPatch,
} from '~/utils/propFilters'

const NO_GAMES: BoardGames = []

type BoardGames = ReadonlyArray<{ gameId: number, awayTeam: string, homeTeam: string }>

/** A daily board's player, team and game filters, kept in the URL so Back from a player page restores them. */
export function useBoardFilters(games: BoardGames = NO_GAMES) {
  const [params, setParams] = useSearchParams()
  const teams = useMemo(() => gameTeams(games), [games])
  const filter: BoardFilter = useMemo(() => ({
    players: parsePlayerFilter(params),
    team: activeTeamFilter(parseTeamFilter(params.get('team')), teams),
    games: activeGameFilters(parseGameFilters(params), games),
  }), [params, teams, games])
  const update = (patch: PropListFilterPatch) => setParams(withPropListFilters(params, patch), { replace: true })
  return {
    filter,
    teams,
    onPlayers: (player: string[]) => update({ player }),
    onTeam: (team: string) => update({ team }),
    onGames: (game: string[]) => update({ game, team: teamAfterGames(filter.team, game, games) }),
  }
}
