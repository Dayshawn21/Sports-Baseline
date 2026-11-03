import { NbaBoardTable } from '~/components/nba/NbaPropTable'
import { nbaMarketLabel } from '~/utils/nbaLineOnly'
import { nbaPlayerPath } from '~/utils/nbaPlayer'
import type { NbaBoardMarket } from '~/utils/nbaPropBoard'
import { FROM_BOARD } from '~/utils/nflPlayer'

interface Props {
  group: NbaBoardMarket
  date: string
}

/** A row opens the player page on this market and date, marked as a board arrival so the page can return here. */
export default function NbaPropBoardMarket({ group, date }: Props) {
  const modelled = group.rows.filter(item => item.kind === 'modelled')
  const lineOnly = group.rows.filter(item => item.kind === 'line-only')
  const now = new Date()
  const pathFor = (playerId: number) => nbaPlayerPath(playerId, { date, market: group.market })
  return <section className="prop-table-panel nba-prop-board__rows" aria-label={`${nbaMarketLabel(group.market)} lines`}>
    {group.rows.length === 0 && <p className="nfl-empty">No {nbaMarketLabel(group.market).toLowerCase()} lines on this date.</p>}
    {modelled.length > 0 && <NbaBoardTable kind="modelled" market={group.market} rows={modelled} now={now} pathFor={pathFor} linkState={FROM_BOARD} />}
    {lineOnly.length > 0 && <NbaBoardTable kind="line-only" market={group.market} rows={lineOnly} now={now} pathFor={pathFor} linkState={FROM_BOARD} />}
  </section>
}
