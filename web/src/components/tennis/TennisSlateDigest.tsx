import { SlateDigest } from '~/components/shared/SlateDigest'
import { SlateNoPicks } from '~/components/shared/SlateNoPicks'
import { Link } from 'react-router-dom'
import { leanLink, type TennisDigestItem, type TennisLeanDigestItem } from '~/utils/tennisSlate'

interface Props {
  priced: TennisDigestItem[]
  leans: TennisLeanDigestItem[]
  /** "12 matches to start · next Tue 9:00 AM CT", under the no-picks headline. */
  remaining: string
}

/**
 * A slate with a priced best bet shows those picks as boxes, the only green on the digest (their EV).
 * Otherwise it says there are no picks and lists the next matches' model leans as one gray line, unranked:
 * a box reads as a pick, and a lean is not one.
 */
export default function TennisSlateDigest({ priced, leans, remaining }: Props) {
  if (priced.length > 0) return <SlateDigest label="Best picks · priced" labelId="tennis-digest-label">
    {priced.map((item) => {
      return <Link key={item.matchKey} to={item.analysisPath} className="slate-digest__play tennis-digest__play">
        <strong>{item.pick}</strong>
        <span className="slate-digest__what">{item.what}</span>
        <span className="slate-digest__what">{item.when}</span>
        <span className="slate-digest__num"><span>{item.odds}</span><span className="tennis-digest__ev">{item.ev} EV</span></span>
        <span className="tennis-digest__foot">
          <span className={`tennis-tier is-${item.tier.toLowerCase()}`}>{item.tier}</span>
          {item.tone && <span className={`tennis-tour-tag is-${item.tone}`}>{item.tourLabel}</span>}
        </span>
      </Link>
    })}
  </SlateDigest>
  return <SlateNoPicks sport="tennis" title="No tennis picks" remaining={remaining}
    gaps={leans.map(leanLink)} gapsLabel="Model leans" gapsOrder="the next matches to start" />
}
