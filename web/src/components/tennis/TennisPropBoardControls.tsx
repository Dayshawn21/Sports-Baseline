import { Switch } from 'antd'
import SportViewSwitch from '~/components/shared/SportViewSwitch'
import type { TennisBoardCategory, TennisPropSource, TennisTourFilter } from '~/utils/tennisPropBoard'
import { TENNIS_PROP_SOURCES, TENNIS_TOUR_FILTERS } from '~/utils/tennisPropBoard'

export function PropBoardHead({ lines, rateable, markets }: { lines: number, rateable: number, markets: number }) {
  return <header className="tennis-prop-board__head">
    <div>
      <div className="unified-eyebrow">Tennis · Prop board</div>
      <h1 className="unified-page-title">Best picks by category</h1>
      <p className="unified-page-subtitle">Current player and match lines, grouped by market and ranked by priced model EV.</p>
    </div>
    <div className="tennis-prop-board__aside">
      <SportViewSwitch sport="tennis" />
      <section className="tennis-prop-summary" aria-label="Prop board summary">
        <div className="tennis-prop-stat"><span className="tennis-prop-stat__label">Lines</span><strong className="tennis-prop-stat__value">{lines}</strong><span className="tennis-prop-stat__sub">current 24-hour slate</span></div>
        <div className="tennis-prop-stat"><span className="tennis-prop-stat__label">Rateable</span><strong className="tennis-prop-stat__value">{rateable}</strong><span className="tennis-prop-stat__sub">across {markets} markets</span></div>
      </section>
    </div>
  </header>
}

export function MarketPills({ categories, selected, onSelect }: { categories: TennisBoardCategory[], selected: string, onSelect: (market: string) => void }) {
  return <nav className="tennis-prop-pills" aria-label="Tennis prop categories">
    {categories.map(category => <button key={category.market} type="button" className={category.market === selected ? 'is-selected' : ''} aria-pressed={category.market === selected} onClick={() => onSelect(category.market)}>
      {category.label}<em>{category.rateable.length}</em>
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
    <label className="tennis-prop-toggle"><Switch size="small" checked={showAll} onChange={onShowAll} /><span>Show all lines</span></label>
  </section>
}
