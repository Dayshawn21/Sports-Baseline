import { Link } from 'react-router-dom'
import { SlateDigest } from '~/components/shared/SlateDigest'
import type { NflSlateDigestItem } from '~/utils/nflSlate'

/** The week's largest prop gaps; gray reference, never a pick until the ranking check adopts a slice. */
export function NflSlateDigest({ items }: { items: NflSlateDigestItem[] }) {
  if (items.length === 0) return null
  return <SlateDigest label="Largest gaps this week · reference, not picks" labelId="nfl-digest-label">
    {items.map(item => <Link key={item.lineId} className="slate-digest__play" to={`/nfl/game/${item.gameId}`}
      aria-label={`${item.playerName}, ${item.market}, ${item.matchup}, open game page`}>
      <strong>{item.playerName}</strong>
      <span className="slate-digest__what">{item.market} · {item.matchup}</span>
      <span className="slate-digest__num"><span>line {item.line}</span><span>model {item.model}</span></span>
      <span className="slate-digest__gap">gap {item.gap}</span>
    </Link>)}
  </SlateDigest>
}
