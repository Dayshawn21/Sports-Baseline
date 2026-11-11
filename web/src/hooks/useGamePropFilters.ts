import { useSearchParams } from 'react-router-dom'
import { ALL, activeTeamFilter, isFiltering, parsePlayerQuery, parseTeamFilter, withPropFilters, type GamePropFilter, type PropFilterPatch } from '~/utils/propFilters'

/** A game page's player search and team toggle, kept in the URL so Back from a player page restores them. */
export function useGamePropFilters(game: { awayTeam: string, homeTeam: string }) {
  const [params, setParams] = useSearchParams()
  const filter: GamePropFilter = {
    q: parsePlayerQuery(params.get('q')),
    team: activeTeamFilter(parseTeamFilter(params.get('team')), [game.awayTeam, game.homeTeam]),
  }
  const update = (patch: PropFilterPatch) => setParams(withPropFilters(params, patch), { replace: true })
  return {
    filter,
    filtering: isFiltering({ ...filter, game: ALL }),
    onQuery: (q: string) => update({ q }),
    onTeam: (team: string) => update({ team }),
  }
}
