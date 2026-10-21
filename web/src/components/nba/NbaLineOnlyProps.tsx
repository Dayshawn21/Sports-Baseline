import { Drawer } from 'antd'
import { useRef, useState } from 'react'
import NbaPropEvidencePanel from '~/components/nba/NbaPropEvidencePanel'
import { NbaLineOnlyTable } from '~/components/nba/NbaPropTable'
import { useIsMobile } from '~/hooks/useIsMobile'
import { useNbaLineOnlyProps } from '~/hooks/useNba'
import { nbaLineOnlyGroups, nbaMarketLabel } from '~/utils/nbaLineOnly'
import { UNAVAILABLE_NBA_INJURIES } from '~/utils/nbaInjuries'

/** Stored PrizePicks lines with recent results. Display only: no projection, edge, rank or signal color until 20g. */
export function NbaLineOnlyProps({ gameId, startUtc }: { gameId: number, startUtc: string | null }) {
  const [selection, setSelected] = useState<{ market: string, playerId: number } | null>(null)
  const section = useRef<HTMLElement>(null)
  const opener = useRef<HTMLButtonElement | null>(null)
  const open = (market: string, playerId: number) => {
    opener.current = section.current?.querySelector<HTMLButtonElement>(`[data-row-key="${CSS.escape(`${market}:${playerId}`)}"] button`) ?? null
    setSelected({ market, playerId })
  }
  const restoreFocus = () => requestAnimationFrame(() => {
    if (opener.current?.isConnected) opener.current.focus({ preventScroll: true })
  })
  const isMobile = useIsMobile()
  const query = useNbaLineOnlyProps(gameId)
  const groups = query.data ? nbaLineOnlyGroups(query.data.lines) : []
  const selected = selection && groups.find(group => group.market === selection.market)?.rows.find(row => row.playerId === selection.playerId)
  const injuryReport = query.data?.injuryReport ?? UNAVAILABLE_NBA_INJURIES
  const now = new Date()
  if (query.isSuccess && groups.length === 0) return null
  return <section ref={section} className="nfl-line-only" aria-label="Other lines">
    <h3 className="nfl-game-label">Other lines <small>not modelled · recent results only</small></h3>
    {query.isLoading && <p className="nfl-line-only__status">Loading lines...</p>}
    {query.isError && <p className="nfl-line-only__status">Lines could not load.</p>}
    {groups.map(group => <div key={group.market} className="nfl-line-only__market prop-table-panel">
      <h4>{nbaMarketLabel(group.market)}</h4>
      <NbaLineOnlyTable market={group.market} rows={group.rows}
        selectedPlayerId={selection?.market === group.market ? selected?.playerId ?? null : null}
        onOpen={row => open(group.market, row.playerId)}
        injuryReport={injuryReport} startUtc={startUtc} now={now} />
    </div>)}
    <Drawer open={!!selected} onClose={() => { setSelected(null); restoreFocus() }} width={isMobile ? '100%' : 460} title={null}
      afterOpenChange={isOpen => { if (!isOpen) restoreFocus() }}
      className="nfl-slate nba-prop-drawer" destroyOnHidden>
      {selected && selection && <NbaPropEvidencePanel kind="line-only" market={selection.market} row={selected} injuryReport={injuryReport} startUtc={startUtc} teamStats={query.data?.teamStats ?? null} />}
    </Drawer>
  </section>
}
