import { Drawer } from 'antd'
import { useState } from 'react'
import NbaPropEvidencePanel from '~/components/nba/NbaPropEvidencePanel'
import { NbaPropTable } from '~/components/nba/NbaPropTable'
import { useIsMobile } from '~/hooks/useIsMobile'
import { useNbaProps } from '~/hooks/useNba'
import { nbaMarketLabel } from '~/utils/nbaLineOnly'
import { nbaPropGroups } from '~/utils/nbaProps'
import { UNAVAILABLE_NBA_INJURIES } from '~/utils/nbaInjuries'

/** Modelled PrizePicks lines with the reference projection (20g2). Gray: no pick, rank or signal color until 20g4. */
export function NbaProps({ gameId, startUtc }: { gameId: number, startUtc: string | null }) {
  const [selection, setSelected] = useState<{ market: string, playerId: number } | null>(null)
  const isMobile = useIsMobile()
  const query = useNbaProps(gameId)
  const groups = query.data ? nbaPropGroups(query.data.lines) : []
  const selected = selection && groups.find(group => group.market === selection.market)?.cards.find(card => card.playerId === selection.playerId)
  const injuryReport = query.data?.injuryReport ?? UNAVAILABLE_NBA_INJURIES
  const now = new Date()
  if (query.isSuccess && groups.length === 0) return null
  return <section className="nfl-line-only nba-props" aria-label="Props">
    <h3 className="nfl-game-label">Props <small>reference projection · gray until the ranking check adopts a slice</small></h3>
    {query.isLoading && <p className="nfl-line-only__status">Loading props...</p>}
    {query.isError && <p className="nfl-line-only__status">Props could not load.</p>}
    {groups.map(group => <div key={group.market} className="nfl-line-only__market prop-table-panel">
      <h4>{nbaMarketLabel(group.market)}</h4>
      <NbaPropTable market={group.market} cards={group.cards}
        selectedPlayerId={selection?.market === group.market ? selected?.playerId ?? null : null}
        onOpen={card => setSelected({ market: group.market, playerId: card.playerId })}
        injuryReport={injuryReport} startUtc={startUtc} now={now} />
    </div>)}
    <Drawer open={!!selected} onClose={() => setSelected(null)} width={isMobile ? '100%' : 460} title={null}
      className="nfl-slate nba-prop-drawer" destroyOnHidden>
      {selected && selection && query.data && <NbaPropEvidencePanel kind="modelled" market={selection.market} row={selected} modelVersion={query.data.modelVersion} injuryReport={injuryReport} startUtc={startUtc} />}
    </Drawer>
  </section>
}
