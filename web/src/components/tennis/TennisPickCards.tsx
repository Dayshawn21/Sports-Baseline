import type { FeaturedPick } from '~/utils/tennisSlate'
import { fmtEv, tourTone } from '~/utils/tennisSlate'
import { unifiedMatchToPrediction } from '~/utils/unifiedTennis'
import { fmtAmerican, fmtPct } from '~/utils/odds'
import { fmtStartCT, fmtTournament } from '~/utils/format'

interface Props {
  picks: FeaturedPick[]
  selectedMatchKey: string | null
  onSelectMatch: (matchKey: string) => void
}

function PickCard({ featured, selected, onSelect }: { featured: FeaturedPick; selected: boolean; onSelect: () => void }) {
  const { match, pick } = featured
  const prediction = unifiedMatchToPrediction(match)
  const tone = tourTone(prediction?.tour, prediction?.tourLabel)
  const tier = pick.confidence.toLowerCase()
  return (
    <button type="button" className={`tennis-pick-card${selected ? ' is-selected' : ''}`} onClick={onSelect} aria-pressed={selected}>
      <span className="tennis-pick-card__head">
        <strong>{pick.pick}</strong>
        {tone && <span className={`tennis-tour-tag is-${tone}`}>{prediction?.tourLabel ?? prediction?.tour}</span>}
      </span>
      <span className="tennis-pick-card__meta">
        {pick.label}{prediction ? ` · ${prediction.p1Name} vs ${prediction.p2Name}` : ''}
      </span>
      <span className="tennis-pick-card__meta">
        {fmtTournament(prediction?.tournament ?? null)} · {fmtStartCT(prediction?.startUtc) ?? 'Time TBA'}
      </span>
      <span className="tennis-pick-card__ev">{fmtEv(pick.evPct)}<small>EV</small></span>
      <span className="tennis-pick-card__row"><span>Model</span><span>{fmtPct(pick.modelProb)}</span></span>
      <span className="tennis-pick-card__row"><span>Market</span><span>{fmtPct(pick.marketProb)}</span></span>
      <span className="tennis-pick-card__foot">
        <span>{fmtAmerican(pick.oddsAmerican)}</span>
        <span className={`tennis-tier is-${tier}`}>{pick.confidence}</span>
      </span>
    </button>
  )
}

/** The first best bet of each of the top matches, in the page's sort order. */
export default function TennisPickCards({ picks, selectedMatchKey, onSelectMatch }: Props) {
  if (picks.length === 0) return null
  return (
    <section className="tennis-pick-cards" aria-label="Best picks">
      <h2 className="tennis-slate-section">Best picks</h2>
      <div className="tennis-pick-cards__grid">
        {picks.map((featured) => (
          <PickCard
            key={featured.match.key}
            featured={featured}
            selected={featured.match.key === selectedMatchKey}
            onSelect={() => onSelectMatch(featured.match.key)}
          />
        ))}
      </div>
    </section>
  )
}
