import { Link } from 'react-router-dom'
import './slate-gaps.css'

export interface SlateGapLink {
  key: string
  to: string
  playerName: string
  market: string
  /** Left out where the item has no number (a tennis lean). */
  gap?: string | null
  /** The share the strip ranks by ("104%"), shown after the gap so the order reads true. */
  share?: string | null
  /** A reason the line ranks lower than its share alone suggests ("7 games"). */
  note?: string | null
  ariaLabel: string
  /** For the slate's opened-row memory. */
  openKey?: string
  onOpen?: () => void
}

interface Props {
  gaps: SlateGapLink[]
  /** The strip's name and how it is ordered, in the sport's own rule. */
  label: string
  order: string
  /** Set where the strip leads a page section on its own, without the "No picks" headline. */
  lead?: boolean
}

/** Reference items as one gray line: a box reads as a pick, and these are not picks. */
export function SlateGaps({ gaps, label, order, lead = false }: Props) {
  if (gaps.length === 0) return null
  return <section className={lead ? 'slate-gaps is-lead' : 'slate-gaps'} aria-label={label}>
    <p className="slate-gaps__label">{label} <span className="slate-gaps__note">reference, not picks · {order}</span></p>
    <ul className="slate-gaps__list">
      {gaps.map(gap => <li key={gap.key}>
        <Link className="slate-gaps__item" to={gap.to} aria-label={gap.ariaLabel} data-open-key={gap.openKey} onClick={gap.onOpen}>
          <strong>{gap.playerName}</strong> <span className="slate-gaps__market">{gap.market}</span>
          {gap.gap && <>{' '}<span className="slate-gaps__gap">{gap.gap}</span></>}
          {gap.share && <>{' '}<span className="slate-gaps__share">{gap.share}</span></>}
          {gap.note && <>{' '}<span className="slate-gaps__extra">{gap.note}</span></>}
        </Link>
      </li>)}
    </ul>
  </section>
}
