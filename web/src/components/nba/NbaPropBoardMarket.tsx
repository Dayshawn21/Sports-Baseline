import { useCallback, useMemo } from 'react'
import { NbaBoardTable } from '~/components/nba/NbaPropTable'
import { useRowBatches } from '~/hooks/useRowBatches'
import { nbaMarketLabel } from '~/utils/nbaLineOnly'
import { nbaPlayerPath } from '~/utils/nbaPlayer'
import type { NbaBoardMarket } from '~/utils/nbaPropBoard'
import { FROM_BOARD } from '~/utils/playerPage'
import { splitRowLimit } from '~/utils/rowBatches'

interface Props {
  group: NbaBoardMarket
  date: string
}

/** A row opens the player page on this market and date, marked as a board arrival so the page can return here. */
export default function NbaPropBoardMarket({ group, date }: Props) {
  const modelled = group.rows.filter(item => item.kind === 'modelled')
  const lineOnly = group.rows.filter(item => item.kind === 'line-only')
  // Stable across row batches so the memoized rows skip re-rendering; a new group (filters) still refreshes the clock.
  const now = useMemo(() => new Date(), [group])
  const pathFor = useCallback((playerId: number) => nbaPlayerPath(playerId, { date, market: group.market }), [date, group.market])
  const [modelledShown, lineOnlyShown] = splitRowLimit(useRowBatches(group.rows.length), modelled.length)
  return <section className="prop-table-panel nba-prop-board__rows" aria-label={`${nbaMarketLabel(group.market)} lines`}>
    {group.rows.length === 0 && <p className="nfl-empty">No {nbaMarketLabel(group.market).toLowerCase()} lines on this date.</p>}
    {modelledShown > 0 && <NbaBoardTable kind="modelled" market={group.market} rows={modelled} shown={modelledShown} now={now} pathFor={pathFor} linkState={FROM_BOARD} />}
    {lineOnlyShown > 0 && <NbaBoardTable kind="line-only" market={group.market} rows={lineOnly} shown={lineOnlyShown} now={now} pathFor={pathFor} linkState={FROM_BOARD} />}
  </section>
}
