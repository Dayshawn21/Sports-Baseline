import { Link } from 'react-router-dom'
import { SlateDigest } from '~/components/shared/SlateDigest'
import type { NflSlateDigestItem } from '~/utils/nflSlate'

interface Props {
  items: NflSlateDigestItem[]
  scope?: string
  /** On a game page the box opens the line's drawer instead of linking to the page already open. */
  onOpen?: (item: NflSlateDigestItem, box: HTMLButtonElement) => void
}

/** The week's largest prop gaps; gray reference, never a pick until the ranking check adopts a slice. */
export function NflSlateDigest({ items, scope = 'this week', onOpen }: Props) {
  if (items.length === 0) return null
  return <SlateDigest label={`Largest gaps ${scope} · reference, not picks`} labelId="nfl-digest-label">
    {items.map(item => {
      const body = <>
        <strong>{item.playerName}</strong>
        <span className="slate-digest__what">{item.market} · {item.matchup}</span>
        <span className="slate-digest__num"><span>line {item.line}</span><span>{item.modelLabel ?? 'model'} {item.model}</span></span>
        <span className="slate-digest__gap">gap {item.gap}</span>
      </>
      return onOpen
        ? <button key={item.lineId} type="button" className="slate-digest__play" onClick={event => onOpen(item, event.currentTarget)}
          aria-label={`${item.playerName}, ${item.market}, open evidence`}>{body}</button>
        : <Link key={item.lineId} className="slate-digest__play" to={`/nfl/game/${item.gameId}`}
          aria-label={`${item.playerName}, ${item.market}, ${item.matchup}, open game page`}>{body}</Link>
    })}
  </SlateDigest>
}
