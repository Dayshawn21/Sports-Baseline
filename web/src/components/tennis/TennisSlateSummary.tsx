interface Props {
  matches: number
  props: number
  locks: number
  strongOrBetter: number
}

/** The page's existing four counts as summary cards; Locks leads because it is the day's play count. */
export default function TennisSlateSummary({ matches, props, locks, strongOrBetter }: Props) {
  return (
    <section className="tennis-slate-summary" aria-label="Slate summary">
      <div className="tennis-slate-stat is-hero">
        <span className="tennis-slate-stat__label">Locks</span>
        <strong className="tennis-slate-stat__value is-positive">{locks}</strong>
        <span className="tennis-slate-stat__sub">of {matches} matches</span>
      </div>
      <div className="tennis-slate-stat">
        <span className="tennis-slate-stat__label">Strong+</span>
        <strong className="tennis-slate-stat__value is-positive">{strongOrBetter}</strong>
        <span className="tennis-slate-stat__sub">Lock and Strong picks and props</span>
      </div>
      <div className="tennis-slate-stat">
        <span className="tennis-slate-stat__label">Props</span>
        <strong className="tennis-slate-stat__value">{props}</strong>
        <span className="tennis-slate-stat__sub">player props</span>
      </div>
      <div className="tennis-slate-stat">
        <span className="tennis-slate-stat__label">Matches</span>
        <strong className="tennis-slate-stat__value">{matches}</strong>
        <span className="tennis-slate-stat__sub">on the slate</span>
      </div>
    </section>
  )
}
