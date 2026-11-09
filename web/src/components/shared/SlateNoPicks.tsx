import { Link } from 'react-router-dom'
import './slate-no-picks.css'

export interface SlateGapLink {
  key: string
  to: string
  playerName: string
  market: string
  gap: string
  ariaLabel: string
  /** For the slate's opened-row memory, which the boxed digest also used. */
  openKey?: string
  onOpen?: () => void
}

interface Props {
  sport: string
  /** What is left of the slate: "1 game left · Mon 7:15 PM CT". */
  remaining: string
  gaps: SlateGapLink[]
}

/** A slate with no adopted picks says so first; the largest gaps follow as one gray reference line, never a pick. */
export function SlateNoPicks({ sport, remaining, gaps }: Props) {
  return <section className="slate-no-picks" aria-labelledby={`${sport}-no-picks`}>
    <div className="slate-no-picks__head">
      <h2 id={`${sport}-no-picks`} className="slate-no-picks__title">No {sport.toUpperCase()} picks</h2>
      {remaining && <p className="slate-no-picks__left">{remaining}</p>}
    </div>
    {gaps.length > 0 && <div className="slate-gaps">
      <span className="slate-gaps__label">Largest gaps <span className="slate-gaps__note">reference, not picks</span></span>
      <ul className="slate-gaps__list">
        {gaps.map(gap => <li key={gap.key}>
          <Link className="slate-gaps__item" to={gap.to} aria-label={gap.ariaLabel} data-open-key={gap.openKey} onClick={gap.onOpen}>
            <strong>{gap.playerName}</strong> <span className="slate-gaps__market">{gap.market}</span> <span className="slate-gaps__gap">{gap.gap}</span>
          </Link>
        </li>)}
      </ul>
    </div>}
  </section>
}
