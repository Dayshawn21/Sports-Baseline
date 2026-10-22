import { Select, Switch } from 'antd'
import PageHead from '~/components/shared/PageHead'
import type { NflPropGame } from '~/types/nfl'
import { NFL_SEASON_OPTIONS, NFL_WEEK_OPTIONS, formatKickoffTime, marketLabel } from '~/utils/nflLabels'
import type { NflBoardCategory } from '~/utils/nflPropBoard'
import { NFL_POSITION_OPTIONS, type NflPositionFilter } from '~/utils/nflPositions'
import { isTargetsReference } from '~/utils/nflTargets'

interface HeadProps {
  season: number
  week: number
  games: number
  categories: NflBoardCategory[]
  lineOnlyCount?: number
  onSeason: (season: number) => void
  onWeek: (week: number) => void
}

export function NflPropBoardHead({ season, week, games, categories, lineOnlyCount = 0, onSeason, onWeek }: HeadProps) {
  const comparisons = categories.filter(category => !isTargetsReference(category.market))
  const rateable = comparisons.reduce((total, category) => total + category.rateable.length, 0)
  const references = categories.filter(category => isTargetsReference(category.market)).reduce((total, category) => total + category.rateable.length, 0)
  return <PageHead
    title="NFL props"
    meta={`${season} · Week ${week}`}
    actions={<>
      <Select aria-label="Season" value={season} onChange={onSeason} options={NFL_SEASON_OPTIONS} />
      <Select aria-label="Week" value={week} onChange={onWeek} options={NFL_WEEK_OPTIONS} />
    </>}
    stats={<section className="nfl-prop-summary" aria-label="Prop board summary">
      <div className="nfl-prop-stat"><span className="nfl-prop-stat__label">Games</span><strong className="nfl-prop-stat__value">{games}</strong><span className="nfl-prop-stat__sub">upcoming with lines</span></div>
      <div className="nfl-prop-stat"><span className="nfl-prop-stat__label">Rateable</span><strong className="nfl-prop-stat__value">{rateable}</strong><span className="nfl-prop-stat__sub">across {comparisons.length} markets{references > 0 ? ` · ${references} reference lines` : ''}</span></div>
      <div className="nfl-prop-stat"><span className="nfl-prop-stat__label">Other markets</span><strong className="nfl-prop-stat__value">{lineOnlyCount}</strong><span className="nfl-prop-stat__sub">recent results only</span></div>
    </section>}
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
  gameFilter: string
  games: NflPropGame[]
  showAll: boolean
  showLineToggle?: boolean
  onPosition: (position: NflPositionFilter) => void
  onGame: (game: string) => void
  onShowAll: (showAll: boolean) => void
}

function gameOption(game: NflPropGame) {
  const kickoff = formatKickoffTime(game.startUtc)
  return { value: String(game.gameId), label: `${game.awayTeam} @ ${game.homeTeam}${kickoff ? ` · ${kickoff}` : ''}` }
}

export function NflPropBoardFilters({ position, gameFilter, games, showAll, showLineToggle = true, onPosition, onGame, onShowAll }: FilterProps) {
  return <section className="nfl-prop-filter-bar" aria-label="Board filters">
    <div className="nfl-prop-seg" role="group" aria-label="Position">
      {NFL_POSITION_OPTIONS.map(option => <button key={option.value} type="button" className={position === option.value ? 'is-selected' : ''} aria-pressed={position === option.value} onClick={() => onPosition(option.value)}>{option.label}</button>)}
    </div>
    <Select aria-label="Game" value={gameFilter} onChange={onGame} options={[{ value: 'all', label: 'All games' }, ...games.map(gameOption)]} />
    {showLineToggle && <label className="nfl-prop-toggle"><Switch size="small" checked={showAll} onChange={onShowAll} /><span>Show all lines</span></label>}
  </section>
}
