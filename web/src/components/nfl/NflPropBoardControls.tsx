import { Select, Switch } from 'antd'
import PageHead from '~/components/shared/PageHead'
import type { NflSlateGame } from '~/types/nfl'
import { NFL_SEASON_OPTIONS, NFL_WEEK_OPTIONS, formatKickoffTime, marketLabel } from '~/utils/nflLabels'
import type { NflBoardCategory } from '~/utils/nflPropBoard'
import { NFL_POSITION_OPTIONS, type NflPositionFilter } from '~/utils/nflPositions'

interface HeadProps {
  season: number
  week: number
  games: number
  categories: NflBoardCategory[]
  onSeason: (season: number) => void
  onWeek: (week: number) => void
}

export function NflPropBoardHead({ season, week, games, categories, onSeason, onWeek }: HeadProps) {
  const rateable = categories.reduce((total, category) => total + category.rateable.length, 0)
  return <PageHead
    title="NFL props"
    meta={`${season} · Week ${week}`}
    actions={<>
      <Select aria-label="Season" value={season} onChange={onSeason} options={NFL_SEASON_OPTIONS} />
      <Select aria-label="Week" value={week} onChange={onWeek} options={NFL_WEEK_OPTIONS} />
    </>}
    stats={<section className="nfl-prop-summary" aria-label="Prop board summary">
      <div className="nfl-prop-stat"><span className="nfl-prop-stat__label">Games</span><strong className="nfl-prop-stat__value">{games}</strong><span className="nfl-prop-stat__sub">upcoming with lines</span></div>
      <div className="nfl-prop-stat"><span className="nfl-prop-stat__label">Rateable</span><strong className="nfl-prop-stat__value">{rateable}</strong><span className="nfl-prop-stat__sub">across {categories.length} markets</span></div>
    </section>}
  />
}

export function NflMarketPills({ categories, selected, onSelect }: { categories: NflBoardCategory[], selected: string, onSelect: (market: string) => void }) {
  return <nav className="nfl-prop-pills" aria-label="Prop categories">
    {categories.map(category => <button key={category.market} type="button" className={[category.market === selected && 'is-selected', category.rateable.length === 0 && 'is-empty'].filter(Boolean).join(' ')} aria-pressed={category.market === selected} onClick={() => onSelect(category.market)}>
      {marketLabel(category.market)}<em>{category.rateable.length}</em>
    </button>)}
  </nav>
}

interface FilterProps {
  position: NflPositionFilter
  gameFilter: string
  games: NflSlateGame[]
  showAll: boolean
  onPosition: (position: NflPositionFilter) => void
  onGame: (game: string) => void
  onShowAll: (showAll: boolean) => void
}

function gameOption(game: NflSlateGame) {
  const kickoff = formatKickoffTime(game.startUtc)
  return { value: String(game.gameId), label: `${game.awayTeam} @ ${game.homeTeam}${kickoff ? ` · ${kickoff}` : ''}` }
}

export function NflPropBoardFilters({ position, gameFilter, games, showAll, onPosition, onGame, onShowAll }: FilterProps) {
  return <section className="nfl-prop-filter-bar" aria-label="Board filters">
    <div className="nfl-prop-seg" role="group" aria-label="Position">
      {NFL_POSITION_OPTIONS.map(option => <button key={option.value} type="button" className={position === option.value ? 'is-selected' : ''} aria-pressed={position === option.value} onClick={() => onPosition(option.value)}>{option.label}</button>)}
    </div>
    <Select aria-label="Game" value={gameFilter} onChange={onGame} options={[{ value: 'all', label: 'All games' }, ...games.map(gameOption)]} />
    <label className="nfl-prop-toggle"><Switch size="small" checked={showAll} onChange={onShowAll} /><span>Show all lines</span></label>
  </section>
}
