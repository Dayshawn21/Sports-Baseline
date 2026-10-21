import { Drawer } from 'antd'
import { useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import NbaPropEvidencePanel from '~/components/nba/NbaPropEvidencePanel'
import { NbaBoardTable } from '~/components/nba/NbaPropTable'
import { useIsMobile } from '~/hooks/useIsMobile'
import { nbaMarketLabel } from '~/utils/nbaLineOnly'
import type { NbaBoardMarket, NbaBoardRow } from '~/utils/nbaPropBoard'

interface Props {
  group: NbaBoardMarket
  modelVersion: string
}

export default function NbaPropBoardMarket({ group, modelVersion }: Props) {
  const [selectedKey, setSelectedKey] = useState<string | null>(null)
  const section = useRef<HTMLElement>(null)
  const opener = useRef<HTMLButtonElement | null>(null)
  const isMobile = useIsMobile()
  const selected = group.rows.find(item => item.key === selectedKey) ?? null
  const modelled = group.rows.filter(item => item.kind === 'modelled')
  const lineOnly = group.rows.filter(item => item.kind === 'line-only')
  const now = new Date()
  const open = (item: NbaBoardRow) => {
    opener.current = section.current?.querySelector<HTMLButtonElement>(`[data-row-key="${CSS.escape(item.key)}"] button`) ?? null
    setSelectedKey(item.key)
  }
  const restoreFocus = () => requestAnimationFrame(() => {
    if (opener.current?.isConnected) opener.current.focus({ preventScroll: true })
  })
  return <>
    <section ref={section} className="prop-table-panel nba-prop-board__rows" aria-label={`${nbaMarketLabel(group.market)} lines`}>
      {group.rows.length === 0 && <p className="nfl-empty">No {nbaMarketLabel(group.market).toLowerCase()} lines on this date.</p>}
      {modelled.length > 0 && <NbaBoardTable kind="modelled" market={group.market} rows={modelled} now={now}
        selectedKey={selected?.key ?? null} onOpen={open} />}
      {lineOnly.length > 0 && <NbaBoardTable kind="line-only" market={group.market} rows={lineOnly} now={now}
        selectedKey={selected?.key ?? null} onOpen={open} />}
    </section>
    <Drawer open={selected !== null} onClose={() => { setSelectedKey(null); restoreFocus() }} width={isMobile ? '100%' : 460}
      afterOpenChange={isOpen => {
        // rc-drawer restores its saved focus after this callback returns.
        if (!isOpen) restoreFocus()
      }}
      title={selected ? <Link to={`/nba/game/${selected.game.gameId}`}>{selected.game.awayTeam} @ {selected.game.homeTeam}</Link> : null}
      className="nfl-slate nba-prop-drawer" destroyOnHidden>
      {selected && (selected.kind === 'modelled'
        ? <NbaPropEvidencePanel kind="modelled" market={group.market} row={selected.row} modelVersion={modelVersion} injuryReport={selected.game.injuryReport} startUtc={selected.game.startUtc} />
        : <NbaPropEvidencePanel kind="line-only" market={group.market} row={selected.row} injuryReport={selected.game.injuryReport} startUtc={selected.game.startUtc} />)}
    </Drawer>
  </>
}
