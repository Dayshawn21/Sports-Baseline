import { SlateGaps, type SlateGapLink } from '~/components/shared/SlateGaps'
import { rememberOpened } from '~/hooks/useRestoreOpenedRow'
import { openedRowKey } from '~/utils/nflOpenedRow'
import type { NflSlateDigestItem } from '~/utils/nflSlate'

export const NFL_GAPS_ORDER = '8+ games of history first, then by share of a typical line'

/** One gap in the gray strip; it opens the game page unless `to` says otherwise (the player page). */
export function nflGapLink(item: NflSlateDigestItem, to?: string): SlateGapLink {
  return {
    key: String(item.lineId),
    to: to ?? `/nfl/game/${item.gameId}`,
    playerName: item.playerName,
    market: item.market,
    gap: item.gapUnits,
    share: item.gapShare,
    note: item.shortSample,
    ariaLabel: [
      `${item.playerName}, ${item.market}, ${item.matchup}, gap ${item.gapUnits}`,
      item.gapScaled, item.shortSample && `only ${item.shortSample} of history`, to ? 'open player page' : 'open game page',
    ].filter(Boolean).join(', '),
    openKey: openedRowKey('digest', item.lineId),
    onOpen: () => rememberOpened('digest', item.lineId),
  }
}

interface Props {
  items: NflSlateDigestItem[]
  scope?: string
  /** Where an item goes; defaults to the game page. */
  linkFor?: (item: NflSlateDigestItem) => string
}

/** The largest prop gaps as one gray line; reference, never a pick until the ranking check adopts a slice. */
export function NflSlateDigest({ items, scope = 'this week', linkFor }: Props) {
  return <SlateGaps lead label={`Largest prop gaps ${scope}`} order={NFL_GAPS_ORDER}
    gaps={items.map(item => nflGapLink(item, linkFor?.(item)))} />
}
