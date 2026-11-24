import { SlateGaps, type SlateGapLink } from '~/components/shared/SlateGaps'
import './slate-no-picks.css'

interface Props {
  sport: string
  /** Defaults to "No NFL picks"; a sport whose name is not an acronym passes its own. */
  title?: string
  /** What is left of the slate: "1 game left · Mon 7:15 PM CT". */
  remaining: string
  gaps: SlateGapLink[]
  /** The strip's name and how it is ordered, in the sport's own rule. */
  gapsLabel: string
  gapsOrder: string
}

/** A slate with no adopted picks says so first; the largest gaps follow as one gray reference line, never a pick. */
export function SlateNoPicks({ sport, title, remaining, gaps, gapsLabel, gapsOrder }: Props) {
  return <section className="slate-no-picks" aria-labelledby={`${sport}-no-picks`}>
    <div className="slate-no-picks__head">
      <h2 id={`${sport}-no-picks`} className="slate-no-picks__title">{title ?? `No ${sport.toUpperCase()} picks`}</h2>
      {remaining && <p className="slate-no-picks__left">{remaining}</p>}
    </div>
    <SlateGaps gaps={gaps} label={gapsLabel} order={gapsOrder} />
  </section>
}
