import { Switch } from 'antd'
import PageHead from '~/components/shared/PageHead'
import type { TennisBoardCategory, TennisPropSource, TennisTourFilter } from '~/utils/tennisPropBoard'
import { TENNIS_PROP_SOURCES, TENNIS_TOUR_FILTERS, marketTitle } from '~/utils/tennisPropBoard'

export function PropBoardHead({ lines, rateable, markets }: { lines: number, rateable: number, markets: number }) {
  return <PageHead
    title="Tennis props"
    meta="Next 24 hours"
    stats={<section className="tennis-prop-summary" aria-label="Prop board summary">
      <div className="tennis-prop-stat"><span className="tennis-prop-stat__label">Available lines</span><strong className="tennis-prop-stat__value">{lines}</strong><span className="tennis-prop-stat__sub">rated + review</span></div>
      <div className="tennis-prop-stat"><span className="tennis-prop-stat__label">Rated lines</span><strong className="tennis-prop-stat__value">{rateable}</strong><span className="tennis-prop-stat__sub">gray, unranked · {markets} markets</span></div>
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

function Segment<T extends string>({ label, options, value, onChange }: { label: string, options: Array<{ value: T, label: string }>, value: T, onChange: (value: T) => void }) {
  return <div className="tennis-prop-seg" role="group" aria-label={label}>
    {options.map(option => <button key={option.value} type="button" className={value === option.value ? 'is-selected' : ''} aria-pressed={value === option.value} onClick={() => onChange(option.value)}>{option.label}</button>)}
  </div>
}

interface FilterProps {
  source: TennisPropSource
  tour: TennisTourFilter
  showAll: boolean
  onSource: (source: TennisPropSource) => void
  onTour: (tour: TennisTourFilter) => void
  onShowAll: (showAll: boolean) => void
}

export function PropBoardFilters({ source, tour, showAll, onSource, onTour, onShowAll }: FilterProps) {
  return <section className="tennis-prop-filter-bar" aria-label="Tennis prop board filters">
    <Segment label="Source" options={TENNIS_PROP_SOURCES} value={source} onChange={onSource} />
    <Segment label="Tour" options={TENNIS_TOUR_FILTERS} value={tour} onChange={onTour} />
    <label className="tennis-prop-toggle"><Switch size="small" checked={showAll} onChange={onShowAll} aria-label="Include lines for review" /><span>Include lines for review</span></label>
  </section>
}
