import { Link } from 'react-router-dom'
import { GapDigestBody } from '~/components/shared/GapDigestBody'
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
      const body = <GapDigestBody playerName={item.playerName} market={item.market} matchup={item.matchup}
        when={item.when} line={item.line} model={item.model} gap={item.gap} modelLabel={item.modelLabel} />
      return onOpen
        ? <button key={item.lineId} type="button" className="slate-digest__play" onClick={event => onOpen(item, event.currentTarget)}
          aria-label={`${item.playerName}, ${item.market}, open evidence`}>{body}</button>
        : <Link key={item.lineId} className="slate-digest__play" to={`/nfl/game/${item.gameId}`}
          aria-label={`${item.playerName}, ${item.market}, ${item.matchup}, open game page`}>{body}</Link>
    })}
  </SlateDigest>
}
