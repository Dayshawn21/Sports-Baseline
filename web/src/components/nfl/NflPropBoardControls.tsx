import { Select, Switch } from 'antd'
import PageHead from '~/components/shared/PageHead'
import GamePicker from '~/components/shared/GamePicker'
import PlayerPicker from '~/components/shared/PlayerPicker'
import type { NflPropGame } from '~/types/nfl'
import { NFL_SEASON_OPTIONS, NFL_WEEK_OPTIONS, formatKickoffTime, marketLabel } from '~/utils/nflLabels'
import { NFL_POSITION_OPTIONS, type NflPositionFilter } from '~/utils/nflPositions'
import { countPart } from '~/utils/slatePeriod'
import { ALL } from '~/utils/propFilters'

interface HeadProps {
  season: number
  week: number
  games: number
  onSeason: (season: number) => void
  onWeek: (week: number) => void
}

export function NflPropBoardHead({ season, week, games, onSeason, onWeek }: HeadProps) {
  return <PageHead
    title="NFL props"
    meta={`${season} · Week ${week} · ${countPart(games, 'game')}`}
    actions={<>
      <Select aria-label="Season" value={season} onChange={onSeason} options={NFL_SEASON_OPTIONS} />
      <Select aria-label="Week" value={week} onChange={onWeek} options={NFL_WEEK_OPTIONS} />
    </>}
  />
}

export function NflMarketPills({ categories, selected, onSelect }: { categories: Array<{ market: string, count: number }>, selected: string | null, onSelect: (market: string) => void }) {
  return <nav className="nfl-prop-pills" aria-label="Prop categories">
    {categories.map(category => <button key={category.market} type="button" className={[category.market === selected && 'is-selected', category.count === 0 && 'is-empty'].filter(Boolean).join(' ')} aria-pressed={category.market === selected} onClick={() => onSelect(category.market)}>
      {marketLabel(category.market)}<em>{category.count}</em>
    </button>)}
  </nav>
}

interface FilterProps {
  position: NflPositionFilter
  gameFilter: string[]
  games: NflPropGame[]
  showAll: boolean
  showLineToggle?: boolean
  players: string[]
  playerNames: string[]
  team: string
  teams: string[]
  onPosition: (position: NflPositionFilter) => void
  onGames: (games: string[]) => void
  onShowAll: (showAll: boolean) => void
  onPlayers: (players: string[]) => void
  onTeam: (team: string) => void
}

function gameOption(game: NflPropGame) {
  const kickoff = formatKickoffTime(game.startUtc)
  return { value: String(game.gameId), label: `${game.awayTeam} @ ${game.homeTeam}${kickoff ? ` · ${kickoff}` : ''}` }
}

export function NflPropBoardFilters({ position, gameFilter, games, showAll, showLineToggle = true, players, playerNames, team, teams, onPosition, onGames, onShowAll, onPlayers, onTeam }: FilterProps) {
  return <section className="nfl-prop-filter-bar" aria-label="Board filters">
    <PlayerPicker options={playerNames} value={players} onChange={onPlayers} />
    <div className="nfl-prop-seg" role="group" aria-label="Position">
      {NFL_POSITION_OPTIONS.map(option => <button key={option.value} type="button" className={position === option.value ? 'is-selected' : ''} aria-pressed={position === option.value} onClick={() => onPosition(option.value)}>{option.label}</button>)}
    </div>
    <Select aria-label="Team" value={team} onChange={onTeam} options={[{ value: ALL, label: 'All teams' }, ...teams.map(code => ({ value: code, label: code }))]} />
    <GamePicker value={gameFilter} onChange={onGames} options={games.map(gameOption)} />
    {showLineToggle && <label className="nfl-prop-toggle"><Switch size="small" checked={showAll} onChange={onShowAll} /><span>Show all lines</span></label>}
  </section>
}
