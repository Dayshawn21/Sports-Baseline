import { Drawer, Select } from 'antd'
import type { MatchDetail } from '~/types/tennis'
import { useAdminView } from '~/hooks/useAdmin'
import { useIsMobile } from '~/hooks/useIsMobile'
import { useMatchView } from '~/hooks/useMatchView'
import { useDKProps, usePrizePicksProps } from '~/hooks/useProps'
import TennisPropEvidencePanel from '~/components/tennis/TennisPropEvidencePanel'
import { TennisPropTable } from '~/components/tennis/TennisPropTable'
import ErrorState from '~/components/shared/ErrorState'
import LoadingState from '~/components/shared/LoadingState'
import { matchPropCategories } from '~/utils/tennisMatchBoard'
import MatchPicks from '~/components/tennis/match/MatchPicks'
import '~/pages/tennis-prop-board.css'

export default function MatchPropsPanel({ detail }: { detail: MatchDetail }) {
  const adminView = useAdminView()
  const mobile = useIsMobile()
  const { view, setView } = useMatchView(detail)
  const { source, player, market, prop: selectedId } = view
  const pp = usePrizePicksProps()
  const dk = useDKProps(source === 'dk')
  const query = source === 'dk' ? dk : pp
  const categories = matchPropCategories(query.data?.props ?? [], detail, source, player === 'all' ? null : player)
  const visible = market === 'all' ? categories : categories.filter(item => item.market === market)
  const selected = visible.flatMap(item => [...item.rateable, ...item.other]).find(line => line.id === selectedId) ?? null
  const count = visible.reduce((total, item) => total + item.rateable.length + item.other.length, 0)
  const unavailableSelection = selectedId != null && !selected && query.isSuccess

  return <div className="tennis-match-prop-panel">
    <MatchPicks detail={detail} />
    <section aria-label="Match prop lines">
      <div className="tennis-match-prop-head"><h2>Prop lines <span>{count}</span></h2><p>All available linked lines, including alternate lines and lines for review. Gray and unranked: rated by P(over) against each payout&apos;s break-even, never picks.</p></div>
      <div className="tennis-match-prop-filters" role="group" aria-label="Match prop filters">
        {adminView && <Select aria-label="Prop source" value={source} onChange={value => setView({ source: value, market: 'all', prop: null })} options={[
          { value: 'prizepicks', label: 'PrizePicks' }, { value: 'dk', label: 'DraftKings' },
        ]} />}
        <Select aria-label="Player" value={player} onChange={value => setView({ player: value, market: 'all', prop: null })} options={[
          { value: 'all', label: 'Both players' }, { value: detail.p1.playerId, label: detail.p1.name }, { value: detail.p2.playerId, label: detail.p2.name },
        ]} />
        <Select aria-label="Market" value={market} onChange={value => setView({ market: value, prop: null })} options={[
          { value: 'all', label: 'All markets' }, ...categories.map(item => ({ value: item.market, label: item.label })),
          ...(market !== 'all' && !categories.some(item => item.market === market) ? [{ value: market, label: 'Unavailable market' }] : []),
        ]} />
      </div>
      {unavailableSelection && <p role="status">The selected line is no longer available for this match and these filters. <button type="button" className="tennis-prop-text-action" onClick={() => setView({ prop: null })}>Clear selection</button></p>}
      {query.isLoading ? <LoadingState message="Loading match prop lines..." />
        : query.isError ? <ErrorState error={query.error} onRetry={() => void query.refetch()} />
        : visible.length === 0 ? <p className="tennis-match-empty">No current prop lines are available for this match and these filters. Historical lines may no longer be on the provider board.</p>
        : visible.map(category => <section key={category.market} className="prop-table-panel" aria-label={`${category.label} prop lines`}>
          <h3>{category.label}</h3>
          <TennisPropTable category={category} tableId={`match-props-${category.market}`} showMatchLinks={false} selectedId={selected?.id ?? null} onOpen={row => setView({ prop: row.id })}
            rateable={category.rateable.map(row => ({ row, rated: true }))}
            other={category.other.map(row => ({ row, rated: false }))} />
        </section>)}
    </section>
    <Drawer open={selected !== null} onClose={() => setView({ prop: null })} width={mobile ? '100%' : 460} title={null}
      aria-label={`Prop evidence for ${selected?.playerName ?? 'selected player'}`} className="tennis-prop-drawer" destroyOnHidden>
      {selected && <TennisPropEvidencePanel row={selected} showMatchLink={false} />}
    </Drawer>
  </div>
}
