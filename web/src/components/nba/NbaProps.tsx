import { Drawer } from 'antd'
import { useState } from 'react'
import NbaPropEvidencePanel from '~/components/nba/NbaPropEvidencePanel'
import { NbaPropTable } from '~/components/nba/NbaPropTable'
import { useIsMobile } from '~/hooks/useIsMobile'
import { useNbaProps } from '~/hooks/useNba'
import { nbaMarketLabel } from '~/utils/nbaLineOnly'
import { nbaPropGroups, type NbaPropCard } from '~/utils/nbaProps'

/** Modelled PrizePicks lines with the reference projection (20g2). Gray: no pick, rank or signal color until 20g4. */
export function NbaProps({ gameId }: { gameId: number }) {
  const [selected, setSelected] = useState<{ market: string, card: NbaPropCard } | null>(null)
  const isMobile = useIsMobile()
  const query = useNbaProps(gameId)
  const groups = query.data ? nbaPropGroups(query.data.lines) : []
  if (query.isSuccess && groups.length === 0) return null
  return <section className="nfl-line-only nba-props" aria-label="Props">
    <h3 className="nfl-game-label">Props <small>reference projection · gray until the ranking check adopts a slice</small></h3>
    {query.isLoading && <p className="nfl-line-only__status">Loading props...</p>}
    {query.isError && <p className="nfl-line-only__status">Props could not load.</p>}
    {groups.map(group => <div key={group.market} className="nfl-line-only__market prop-table-panel">
      <h4>{nbaMarketLabel(group.market)}</h4>
      <NbaPropTable market={group.market} cards={group.cards}
        selectedPlayerId={selected?.market === group.market ? selected.card.playerId : null}
        onOpen={card => setSelected({ market: group.market, card })} />
    </div>)}
    <Drawer open={selected !== null} onClose={() => setSelected(null)} width={isMobile ? '100%' : 460} title={null}
      className="nfl-slate nba-prop-drawer" destroyOnHidden>
      {selected && query.data && <NbaPropEvidencePanel kind="modelled" market={selected.market} row={selected.card} modelVersion={query.data.modelVersion} />}
    </Drawer>
  </section>
}
