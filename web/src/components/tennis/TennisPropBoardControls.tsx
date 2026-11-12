import { Switch } from 'antd'
import PageHead from '~/components/shared/PageHead'
import PlayerPicker from '~/components/shared/PlayerPicker'
import type { TennisBoardCategory, TennisContextFilter, TennisPropSource } from '~/utils/tennisPropBoard'
import { TENNIS_BEST_OF_FILTERS, TENNIS_LINE_TYPE_FILTERS, TENNIS_PROP_SOURCES, TENNIS_SURFACE_FILTERS, TENNIS_TOUR_FILTERS, lineTypeApplies, marketTitle } from '~/utils/tennisPropBoard'

export function PropBoardHead({ lines, rateable, markets }: { lines: number, rateable: number, markets: number }) {
  return <PageHead
    title="Tennis props"
    meta="Next 24 hours"
    stats={<section className="tennis-prop-summary" aria-label="Prop board summary">
      <div className="tennis-prop-stat"><span className="tennis-prop-stat__label">Available lines</span><strong className="tennis-prop-stat__value">{lines}</strong><span className="tennis-prop-stat__sub">rated + review</span></div>
      <div className="tennis-prop-stat"><span className="tennis-prop-stat__label">Rated lines</span><strong className="tennis-prop-stat__value">{rateable}</strong><span className="tennis-prop-stat__sub">ranked only if adopted · {markets} markets</span></div>
    </section>}
  />
}

export function MarketPills({ categories, selected, onSelect }: { categories: TennisBoardCategory[], selected: string, onSelect: (market: string) => void }) {
  return <nav className="tennis-prop-pills" aria-label="Tennis prop categories">
    {categories.map(category => <button key={category.market} type="button" className={[category.market === selected && 'is-selected', category.rateable.length === 0 && 'is-empty'].filter(Boolean).join(' ')} aria-pressed={category.market === selected} onClick={() => onSelect(category.market)}>
      {marketTitle(category.market)}<em>{category.rateable.length} rated / {category.other.length} review</em>
    </button>)}
  </nav>
}

interface SegmentProps<T extends string> {
  label: string
  options: Array<{ value: T, label: string }>
  value: T
  onChange: (value: T) => void
  disabledHint?: string
}

function Segment<T extends string>({ label, options, value, onChange, disabledHint }: SegmentProps<T>) {
  return <div className="tennis-prop-seg" role="group" aria-label={label} title={disabledHint}>
    {options.map(option => <button key={option.value} type="button" className={value === option.value ? 'is-selected' : ''} aria-pressed={value === option.value}
      disabled={disabledHint !== undefined} onClick={() => onChange(option.value)}>{option.label}</button>)}
  </div>
}

interface FilterProps {
  source: TennisPropSource
  filter: TennisContextFilter
  showAll: boolean
  players: string[]
  playerNames: string[]
  onSource: (source: TennisPropSource) => void
  onFilter: (filter: TennisContextFilter) => void
  onShowAll: (showAll: boolean) => void
  onPlayers: (players: string[]) => void
}

export function PropBoardFilters({ source, filter, showAll, players, playerNames, onSource, onFilter, onShowAll, onPlayers }: FilterProps) {
  const lineType = lineTypeApplies(source)
  return <section className="tennis-prop-filter-bar" aria-label="Tennis prop board filters">
    <PlayerPicker options={playerNames} value={players} onChange={onPlayers} />
    <Segment label="Source" options={TENNIS_PROP_SOURCES} value={source} onChange={onSource} />
    <Segment label="Tour" options={TENNIS_TOUR_FILTERS} value={filter.tour} onChange={tour => onFilter({ ...filter, tour })} />
    <Segment label="Surface" options={TENNIS_SURFACE_FILTERS} value={filter.surface} onChange={surface => onFilter({ ...filter, surface })} />
    <Segment label="Format" options={TENNIS_BEST_OF_FILTERS} value={filter.bestOf} onChange={bestOf => onFilter({ ...filter, bestOf })} />
    <Segment label="PrizePicks line type" options={TENNIS_LINE_TYPE_FILTERS} value={lineType ? filter.lineType : 'default'}
      onChange={value => onFilter({ ...filter, lineType: value })} disabledHint={lineType ? undefined : 'Line types are PrizePicks payout tiers; choose All or PrizePicks to use them'} />
    <label className="tennis-prop-toggle"><Switch size="small" checked={showAll} onChange={onShowAll} aria-label="Include lines for review" /><span>Include lines for review</span></label>
  </section>
}
