import { Link } from 'react-router-dom'
import { SlateDigest } from '~/components/shared/SlateDigest'
import type { NbaSlateDigestItem } from '~/utils/nbaSlate'

/** The day's largest reference-projection gaps; gray, never a pick until the ranking check adopts a slice. */
export function NbaSlateDigest({ items }: { items: NbaSlateDigestItem[] }) {
  if (items.length === 0) return null
  return <SlateDigest label="Largest gaps today · reference, not picks" labelId="nba-digest-label">
    {items.map(item => <Link key={item.key} className="slate-digest__play" to={`/nba/game/${item.gameId}`}
      aria-label={`${item.playerName}, ${item.market}, ${item.matchup}, open game page`}>
      <strong>{item.playerName}</strong>
      <span className="slate-digest__what">{item.market} · {item.matchup}</span>
      <span className="slate-digest__num"><span>line {item.line}</span><span>model {item.model}</span></span>
      <span className="slate-digest__gap">gap {item.gap}</span>
    </Link>)}
  </SlateDigest>
}
