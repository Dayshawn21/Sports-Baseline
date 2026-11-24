import { useMemo } from 'react'
import { useSearchParams } from 'react-router-dom'
import { activeTeamFilter, isFiltering, parsePlayerFilter, parseTeamFilter, withPropListFilters, type GamePropFilter, type PropListFilterPatch } from '~/utils/propFilters'

/** A game page's player picker and team toggle, kept in the URL so Back from a player page restores them. */
export function useGamePropFilters({ awayTeam, homeTeam }: { awayTeam: string, homeTeam: string }) {
  const [params, setParams] = useSearchParams()
  const filter: GamePropFilter = useMemo(() => ({
    players: parsePlayerFilter(params),
    team: activeTeamFilter(parseTeamFilter(params.get('team')), [awayTeam, homeTeam]),
  }), [params, awayTeam, homeTeam])
  const update = (patch: PropListFilterPatch) => setParams(withPropListFilters(params, patch), { replace: true })
  return {
    filter,
    filtering: isFiltering({ ...filter, games: [] }),
    onPlayers: (player: string[]) => update({ player }),
    onTeam: (team: string) => update({ team }),
  }
}
