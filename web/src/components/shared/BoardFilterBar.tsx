import { Select } from 'antd'
import type { ReactNode } from 'react'
import GamePicker from '~/components/shared/GamePicker'
import PlayerPicker from '~/components/shared/PlayerPicker'
import { ALL, type BoardFilter } from '~/utils/propFilters'

interface Props {
  games: ReadonlyArray<{ gameId: number, awayTeam: string, homeTeam: string }>
  teams: string[]
  playerNames: string[]
  filter: BoardFilter
  onPlayers: (players: string[]) => void
  onTeam: (team: string) => void
  onGames: (games: string[]) => void
  /** A board's own extra filters, after the game picker. */
  children?: ReactNode
}

export default function BoardFilterBar({ games, teams, playerNames, filter, onPlayers, onTeam, onGames, children }: Props) {
  return <section className="nfl-prop-filter-bar" aria-label="Board filters">
    <PlayerPicker options={playerNames} value={filter.players} onChange={onPlayers} />
    <Select aria-label="Team" value={filter.team} onChange={onTeam}
      options={[{ value: ALL, label: 'All teams' }, ...teams.map(team => ({ value: team, label: team }))]} />
    <GamePicker value={filter.games} onChange={onGames}
      options={games.map(game => ({ value: String(game.gameId), label: `${game.awayTeam} @ ${game.homeTeam}` }))} />
    {children}
  </section>
}
