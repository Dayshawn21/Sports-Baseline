import { Link } from 'react-router-dom'
import { GapDigestBody } from '~/components/shared/GapDigestBody'
import { SlateDigest } from '~/components/shared/SlateDigest'
import { rememberOpened } from '~/hooks/useRestoreOpenedRow'
import { openedRowKey } from '~/utils/nflOpenedRow'
import type { NflSlateDigestItem } from '~/utils/nflSlate'

interface Props {
  items: NflSlateDigestItem[]
  scope?: string
  /** Where a box goes; defaults to the game page. */
  linkFor?: (item: NflSlateDigestItem) => string
}

/** The week's largest prop gaps; gray reference, never a pick until the ranking check adopts a slice. */
export function NflSlateDigest({ items, scope = 'this week', linkFor }: Props) {
  if (items.length === 0) return null
  return <SlateDigest label={`Largest prop gaps ${scope} · reference, not picks`} labelId="nfl-digest-label">
    {items.map(item => {
      const body = <GapDigestBody playerName={item.playerName} market={item.market} matchup={item.matchup}
        when={item.when} line={item.line} model={item.model} gap={item.gap} modelLabel={item.modelLabel} gapScale="as % of a typical line" />
      return linkFor
        ? <Link key={item.lineId} className="slate-digest__play" to={linkFor(item)} data-open-key={openedRowKey('digest', item.lineId)} onClick={() => rememberOpened('digest', item.lineId)}
          aria-label={`${item.playerName}, ${item.market}, open player page`}>{body}</Link>
        : <Link key={item.lineId} className="slate-digest__play" to={`/nfl/game/${item.gameId}`} data-open-key={openedRowKey('digest', item.lineId)} onClick={() => rememberOpened('digest', item.lineId)}
          aria-label={`${item.playerName}, ${item.market}, ${item.matchup}, open game page`}>{body}</Link>
    })}
  </SlateDigest>
}
