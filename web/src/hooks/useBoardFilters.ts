import { useMemo } from 'react'
import { useSearchParams } from 'react-router-dom'
import {
  activeGameFilter, activeTeamFilter, gameTeams, parseGameFilter, parsePlayerQuery, parseTeamFilter, teamAfterGame, withPropFilters, type BoardFilter, type PropFilterPatch,
} from '~/utils/propFilters'

const NO_GAMES: BoardGames = []

type BoardGames = ReadonlyArray<{ gameId: number, awayTeam: string, homeTeam: string }>

/** A daily board's player, team and game filters, kept in the URL so Back from a player page restores them. */
export function useBoardFilters(games: BoardGames = NO_GAMES) {
  const [params, setParams] = useSearchParams()
  const teams = useMemo(() => gameTeams(games), [games])
  const filter: BoardFilter = {
    q: parsePlayerQuery(params.get('q')),
    team: activeTeamFilter(parseTeamFilter(params.get('team')), teams),
    game: activeGameFilter(parseGameFilter(params.get('game')), games),
  }
  const update = (patch: PropFilterPatch) => setParams(withPropFilters(params, patch), { replace: true })
  return {
    filter,
    teams,
    onQuery: (q: string) => update({ q }),
    onTeam: (team: string) => update({ team }),
    onGame: (game: string) => update({ game, team: teamAfterGame(filter.team, game, games) }),
  }
}
