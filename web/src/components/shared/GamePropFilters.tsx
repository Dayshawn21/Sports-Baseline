import PlayerPicker from '~/components/shared/PlayerPicker'
import { ALL, type GamePropFilter } from '~/utils/propFilters'
import '~/pages/nfl-prop-board.css'
import './game-prop-filters.css'

interface Props {
  game: { awayTeam: string, homeTeam: string }
  playerNames: string[]
  filter: GamePropFilter
  onPlayers: (players: string[]) => void
  onTeam: (team: string) => void
}

export default function GamePropFilters({ game, playerNames, filter, onPlayers, onTeam }: Props) {
  const options = [{ value: ALL, label: 'All' }, { value: game.awayTeam, label: game.awayTeam }, { value: game.homeTeam, label: game.homeTeam }]
  return <div className="game-prop-filters" role="group" aria-label="Filter props">
    <PlayerPicker options={playerNames} value={filter.players} onChange={onPlayers} />
    <div className="nfl-prop-seg" role="group" aria-label="Team">
      {options.map(option => <button key={option.value} type="button" className={filter.team === option.value ? 'is-selected' : ''}
        aria-pressed={filter.team === option.value} onClick={() => onTeam(option.value)}>{option.label}</button>)}
    </div>
  </div>
}
