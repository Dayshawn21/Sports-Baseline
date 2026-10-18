import { Drawer } from 'antd'
import { useState } from 'react'
import NbaPropEvidencePanel from '~/components/nba/NbaPropEvidencePanel'
import { NbaLineOnlyTable } from '~/components/nba/NbaPropTable'
import { useIsMobile } from '~/hooks/useIsMobile'
import { useNbaLineOnlyProps } from '~/hooks/useNba'
import { nbaLineOnlyGroups, nbaMarketLabel, type NbaLineOnlyRow } from '~/utils/nbaLineOnly'

/** Stored PrizePicks lines with recent results. Display only: no projection, edge, rank or signal color until 20g. */
export function NbaLineOnlyProps({ gameId }: { gameId: number }) {
  const [selected, setSelected] = useState<{ market: string, row: NbaLineOnlyRow } | null>(null)
  const isMobile = useIsMobile()
  const query = useNbaLineOnlyProps(gameId)
  const groups = query.data ? nbaLineOnlyGroups(query.data.lines) : []
  if (query.isSuccess && groups.length === 0) return null
  return <section className="nfl-line-only" aria-label="Other lines">
    <h3 className="nfl-game-label">Other lines <small>not modelled · recent results only</small></h3>
    {query.isLoading && <p className="nfl-line-only__status">Loading lines...</p>}
    {query.isError && <p className="nfl-line-only__status">Lines could not load.</p>}
    {groups.map(group => <div key={group.market} className="nfl-line-only__market prop-table-panel">
      <h4>{nbaMarketLabel(group.market)}</h4>
      <NbaLineOnlyTable market={group.market} rows={group.rows}
        selectedPlayerId={selected?.market === group.market ? selected.row.playerId : null}
        onOpen={row => setSelected({ market: group.market, row })} />
    </div>)}
    <Drawer open={selected !== null} onClose={() => setSelected(null)} width={isMobile ? '100%' : 460} title={null}
      className="nfl-slate nba-prop-drawer" destroyOnHidden>
      {selected && <NbaPropEvidencePanel kind="line-only" market={selected.market} row={selected.row} />}
    </Drawer>
  </section>
}
