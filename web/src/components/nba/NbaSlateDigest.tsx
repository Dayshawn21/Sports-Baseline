import { Link } from 'react-router-dom'
import { GapDigestBody } from '~/components/shared/GapDigestBody'
import { SlateDigest } from '~/components/shared/SlateDigest'
import type { NbaSlateDigestItem } from '~/utils/nbaSlate'

interface Props {
  items: NbaSlateDigestItem[]
  scope?: string
  /** On a game page a box opens the player's page instead of linking to the game page already open. */
  playerPath?: (item: NbaSlateDigestItem) => string
}

/** The day's largest reference-projection gaps; gray, never a pick until the ranking check adopts a slice. */
export function NbaSlateDigest({ items, scope = 'today', playerPath }: Props) {
  if (items.length === 0) return null
  return <SlateDigest label={`Largest prop gaps ${scope} · reference, not picks`} labelId="nba-digest-label">
    {items.map(item => {
      const body = <GapDigestBody playerName={item.playerName} market={item.market} matchup={item.matchup}
        when={item.when} line={item.line} model={item.model} gap={item.gap} gapDetail={item.gapScaled} />
      return playerPath
        ? <Link key={item.key} className="slate-digest__play" to={playerPath(item)}
          aria-label={`${item.playerName}, ${item.market}, open player page`}>{body}</Link>
        : <Link key={item.key} className="slate-digest__play" to={`/nba/game/${item.gameId}`}
          aria-label={`${item.playerName}, ${item.market}, ${item.matchup}, open game page`}>{body}</Link>
    })}
  </SlateDigest>
}
