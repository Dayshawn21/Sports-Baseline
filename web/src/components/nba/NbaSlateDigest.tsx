import { SlateGaps, type SlateGapLink } from '~/components/shared/SlateGaps'
import type { NbaSlateDigestItem } from '~/utils/nbaSlate'

export const NBA_GAPS_ORDER = 'by share of the line'

/** One gap in the gray strip; it opens the game page unless `to` says otherwise (the player page). */
export function nbaGapLink(item: NbaSlateDigestItem, to?: string): SlateGapLink {
  return {
    key: item.key,
    to: to ?? `/nba/game/${item.gameId}`,
    playerName: item.playerName,
    market: item.market,
    gap: item.gap,
    share: item.gapShare,
    ariaLabel: [`${item.playerName}, ${item.market}, ${item.matchup}, gap ${item.gap}`, item.gapScaled, to ? 'open player page' : 'open game page']
      .filter(Boolean).join(', '),
  }
}

interface Props {
  items: NbaSlateDigestItem[]
  scope?: string
  /** On a game page an item opens the player's page instead of the game page already open. */
  playerPath?: (item: NbaSlateDigestItem) => string
}

/** The largest reference-projection gaps as one gray line; never a pick until the ranking check adopts a slice. */
export function NbaSlateDigest({ items, scope = 'today', playerPath }: Props) {
  return <SlateGaps lead label={`Largest prop gaps ${scope}`} order={NBA_GAPS_ORDER}
    gaps={items.map(item => nbaGapLink(item, playerPath?.(item)))} />
}
