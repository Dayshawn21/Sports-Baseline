import { SlateDigest } from '~/components/shared/SlateDigest'
import { Link } from 'react-router-dom'
import type { TennisDigestItem, TennisLeanDigestItem } from '~/utils/tennisSlate'

interface Props {
  priced: TennisDigestItem[]
  leans: TennisLeanDigestItem[]
}

/**
 * A slate with a priced best bet shows those picks, the only green on the digest (their EV).
 * Otherwise it shows the next matches' model leans, gray and unranked (57d); with neither, nothing.
 */
export default function TennisSlateDigest({ priced, leans }: Props) {
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
  if (leans.length === 0) return null
  return <SlateDigest label="Model leans · reference" labelId="tennis-digest-label">
    {leans.map((item) => <Link key={item.matchKey} to={item.analysisPath} className="slate-digest__play tennis-digest__lean">
      <strong>{item.lean}</strong>
      <span className="slate-digest__what">{item.what}</span>
      <span className="slate-digest__what">{item.when}</span>
    </Link>)}
  </SlateDigest>
}
