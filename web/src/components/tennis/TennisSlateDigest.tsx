import { SlateDigest } from '~/components/shared/SlateDigest'
import { Link } from 'react-router-dom'
import type { TennisDigestItem } from '~/utils/tennisSlate'

interface Props {
  items: TennisDigestItem[]
  selectedKey: string | null
  onSelect: (matchKey: string) => void
}

/** The slate's priced best picks: the only green on a tennis digest box is a priced best bet's EV. */
export default function TennisSlateDigest({ items, selectedKey, onSelect }: Props) {
  if (items.length === 0) return null
  return <SlateDigest label="Best picks · priced" labelId="tennis-digest-label">
    {items.map((item) => {
      const selected = item.matchKey === selectedKey
      const className = `slate-digest__play tennis-digest__play${selected ? ' is-selected' : ''}`
      const content = <>
        <strong>{item.pick}</strong>
        <span className="slate-digest__what">{item.what}</span>
        <span className="slate-digest__what">{item.when}</span>
        <span className="slate-digest__num"><span>{item.odds}</span><span className="tennis-digest__ev">{item.ev} EV</span></span>
        <span className="tennis-digest__foot">
          <span className={`tennis-tier is-${item.tier.toLowerCase()}`}>{item.tier}</span>
          {item.tone && <span className={`tennis-tour-tag is-${item.tone}`}>{item.tourLabel}</span>}
        </span>
      </>
      return item.analysisPath
        ? <Link key={item.matchKey} to={item.analysisPath} className={className}>{content}</Link>
        : <button key={item.matchKey} type="button" aria-pressed={selected}
          className={className} onClick={() => onSelect(item.matchKey)}>{content}</button>
    })}
  </SlateDigest>
}
