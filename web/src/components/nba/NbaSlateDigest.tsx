import { Link } from 'react-router-dom'
import { SlateDigest } from '~/components/shared/SlateDigest'
import type { NbaSlateDigestItem } from '~/utils/nbaSlate'

interface Props {
  items: NbaSlateDigestItem[]
  scope?: string
  /** On a game page the box opens the line's drawer instead of linking to the page already open. */
  onOpen?: (item: NbaSlateDigestItem, box: HTMLButtonElement) => void
}

/** The day's largest reference-projection gaps; gray, never a pick until the ranking check adopts a slice. */
export function NbaSlateDigest({ items, scope = 'today', onOpen }: Props) {
  if (items.length === 0) return null
  return <SlateDigest label={`Largest gaps ${scope} · reference, not picks`} labelId="nba-digest-label">
    {items.map(item => {
      const body = <>
        <strong>{item.playerName}</strong>
        <span className="slate-digest__what">{item.market} · {item.matchup}</span>
        <span className="slate-digest__num"><span>line {item.line}</span><span>model {item.model}</span></span>
        <span className="slate-digest__gap">gap {item.gap}</span>
      </>
      return onOpen
        ? <button key={item.key} type="button" className="slate-digest__play" onClick={event => onOpen(item, event.currentTarget)}
          aria-label={`${item.playerName}, ${item.market}, open evidence`}>{body}</button>
        : <Link key={item.key} className="slate-digest__play" to={`/nba/game/${item.gameId}`}
          aria-label={`${item.playerName}, ${item.market}, ${item.matchup}, open game page`}>{body}</Link>
    })}
  </SlateDigest>
}
