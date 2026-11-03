import { Select } from 'antd'
import type { MatchDetail } from '~/types/tennis'
import { useAdminView } from '~/hooks/useAdmin'
import { useMatchView } from '~/hooks/useMatchView'
import { useDKProps, usePrizePicksProps } from '~/hooks/useProps'
import { TennisPropTable } from '~/components/tennis/TennisPropTable'
import ErrorState from '~/components/shared/ErrorState'
import LoadingState from '~/components/shared/LoadingState'
import { matchPropCategories } from '~/utils/tennisMatchBoard'
import { matchPropsPath } from '~/utils/tennisMatchView'
import { propPlayerPath } from '~/utils/tennisPlayerProps'
import MatchPicks from '~/components/tennis/match/MatchPicks'
import '~/pages/tennis-prop-board.css'

export default function MatchPropsPanel({ detail }: { detail: MatchDetail }) {
  const adminView = useAdminView()
  const { view, setView } = useMatchView(detail)
  const { source, player, market } = view
  const pp = usePrizePicksProps()
  const dk = useDKProps(source === 'dk')
  const query = source === 'dk' ? dk : pp
  const categories = matchPropCategories(query.data?.props ?? [], detail, source, player === 'all' ? null : player)
  const visible = market === 'all' ? categories : categories.filter(item => item.market === market)
  const count = visible.reduce((total, item) => total + item.rateable.length + item.other.length, 0)
  const sides = [{ matchId: detail.matchId, p1Name: detail.p1.name, p2Name: detail.p2.name, p1Id: detail.p1.playerId, p2Id: detail.p2.playerId }]
  const from = matchPropsPath(detail.matchId, view)

  return <div className="tennis-match-prop-panel">
    <MatchPicks detail={detail} />
    <section aria-label="Match prop lines">
      <div className="tennis-match-prop-head"><h2>Prop lines <span>{count}</span></h2><p>All available linked lines, including alternate lines and lines for review. Rated by P(over) against each payout&apos;s break-even, gray and unranked unless a forward check adopts the line&apos;s slice.</p></div>
      <div className="tennis-match-prop-filters" role="group" aria-label="Match prop filters">
        {adminView && <Select aria-label="Prop source" value={source} onChange={value => setView({ source: value, market: 'all' })} options={[
          { value: 'prizepicks', label: 'PrizePicks' }, { value: 'dk', label: 'DraftKings' },
        ]} />}
        <Select aria-label="Player" value={player} onChange={value => setView({ player: value, market: 'all' })} options={[
          { value: 'all', label: 'Both players' }, { value: detail.p1.playerId, label: detail.p1.name }, { value: detail.p2.playerId, label: detail.p2.name },
        ]} />
        <Select aria-label="Market" value={market} onChange={value => setView({ market: value })} options={[
          { value: 'all', label: 'All markets' }, ...categories.map(item => ({ value: item.market, label: item.label })),
          ...(market !== 'all' && !categories.some(item => item.market === market) ? [{ value: market, label: 'Unavailable market' }] : []),
        ]} />
      </div>
      {query.isLoading ? <LoadingState message="Loading match prop lines..." />
        : query.isError ? <ErrorState error={query.error} onRetry={() => void query.refetch()} />
        : visible.length === 0 ? <p className="tennis-match-empty">No current prop lines are available for this match and these filters. Historical lines may no longer be on the provider board.</p>
        : visible.map(category => <section key={category.market} className="prop-table-panel" aria-label={`${category.label} prop lines`}>
          <h3>{category.label}</h3>
          <TennisPropTable category={category} tableId={`match-props-${category.market}`} pathFor={row => propPlayerPath(row, sides)} from={from}
            rateable={category.rateable.map(row => ({ row, rated: true }))}
            other={category.other.map(row => ({ row, rated: false }))} />
        </section>)}
    </section>
  </div>
}
