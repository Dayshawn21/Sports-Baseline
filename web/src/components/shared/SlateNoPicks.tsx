import { Link } from 'react-router-dom'
import './slate-no-picks.css'

export interface SlateGapLink {
  key: string
  to: string
  playerName: string
  market: string
  gap: string
  /** The share the strip ranks by ("104%"), shown after the gap so the order reads true. */
  share?: string | null
  /** A reason the line ranks lower than its share alone suggests ("7 games"). */
  note?: string | null
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
  /** The strip's name and how it is ordered, in the sport's own rule. */
  gapsLabel: string
  gapsOrder: string
}

/** A slate with no adopted picks says so first; the largest gaps follow as one gray reference line, never a pick. */
export function SlateNoPicks({ sport, remaining, gaps, gapsLabel, gapsOrder }: Props) {
  return <section className="slate-no-picks" aria-labelledby={`${sport}-no-picks`}>
    <div className="slate-no-picks__head">
      <h2 id={`${sport}-no-picks`} className="slate-no-picks__title">No {sport.toUpperCase()} picks</h2>
      {remaining && <p className="slate-no-picks__left">{remaining}</p>}
    </div>
    {gaps.length > 0 && <div className="slate-gaps">
      <p className="slate-gaps__label">{gapsLabel} <span className="slate-gaps__note">reference, not picks · {gapsOrder}</span></p>
      <ul className="slate-gaps__list">
        {gaps.map(gap => <li key={gap.key}>
          <Link className="slate-gaps__item" to={gap.to} aria-label={gap.ariaLabel} data-open-key={gap.openKey} onClick={gap.onOpen}>
            <strong>{gap.playerName}</strong> <span className="slate-gaps__market">{gap.market}</span> <span className="slate-gaps__gap">{gap.gap}</span>
            {gap.share && <>{' '}<span className="slate-gaps__share">{gap.share}</span></>}
            {gap.note && <>{' '}<span className="slate-gaps__extra">{gap.note}</span></>}
          </Link>
        </li>)}
      </ul>
    </div>}
  </section>
}
