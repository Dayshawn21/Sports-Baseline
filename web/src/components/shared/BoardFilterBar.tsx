import { Select } from 'antd'
import PlayerSearchInput from '~/components/shared/PlayerSearchInput'
import { ALL, type BoardFilter } from '~/utils/propFilters'

interface Props {
  games: ReadonlyArray<{ gameId: number, awayTeam: string, homeTeam: string }>
  teams: string[]
  filter: BoardFilter
  onQuery: (query: string) => void
  onTeam: (team: string) => void
  onGame: (game: string) => void
}

export default function BoardFilterBar({ games, teams, filter, onQuery, onTeam, onGame }: Props) {
  return <section className="nfl-prop-filter-bar" aria-label="Board filters">
    <PlayerSearchInput value={filter.q} onChange={onQuery} />
    <Select aria-label="Team" value={filter.team} onChange={onTeam}
      options={[{ value: ALL, label: 'All teams' }, ...teams.map(team => ({ value: team, label: team }))]} />
    <Select aria-label="Game" value={filter.game} onChange={onGame}
      options={[{ value: ALL, label: 'All games' }, ...games.map(game => ({ value: String(game.gameId), label: `${game.awayTeam} @ ${game.homeTeam}` }))]} />
  </section>
}
