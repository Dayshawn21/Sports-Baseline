import { useMemo } from 'react'
import { useSearchParams } from 'react-router-dom'
import NbaPropBoardMarket from '~/components/nba/NbaPropBoardMarket'
import ErrorState from '~/components/shared/ErrorState'
import LoadingState from '~/components/shared/LoadingState'
import PageHead from '~/components/shared/PageHead'
import StatChip from '~/components/shared/StatChip'
import { useNbaPropBoard } from '~/hooks/useNba'
import { nbaMarketLabel } from '~/utils/nbaLineOnly'
import { nbaBoardMarket, nbaBoardPath, nbaPropBoard } from '~/utils/nbaPropBoard'
import { parseSlateDate, slateDateLabel } from '~/utils/nbaSlate'
import './nfl-slate.css'
import './nfl-prop-board.css'
import './nba-prop-board.css'

export default function NbaPropBoardPage() {
  const [params, setParams] = useSearchParams()
  const requested = parseSlateDate(params.get('date'))
  const board = useNbaPropBoard(requested)
  const groups = useMemo(() => nbaPropBoard(board.data?.games ?? []), [board.data])
  const market = nbaBoardMarket(params.get('market'), groups)
  const group = groups.find(item => item.market === market)!
  const rowCount = groups.reduce((sum, item) => sum + item.rows.length, 0)
  if (board.isLoading) return <LoadingState message="Loading NBA prop board..." />
  if (board.isError || !board.data) return <ErrorState error={board.error} onRetry={() => void board.refetch()} />
  const { date, previousDate, nextDate, games, modelVersion } = board.data
  const selectMarket = (value: string) => {
    const next = new URLSearchParams(params)
    if (requested === null) next.delete('date')
    next.set('market', value)
    setParams(next)
  }
  return <div className="page-shell nfl-slate nba-prop-board"><div className="page-container is-wide">
    <PageHead title="NBA props" meta={slateDateLabel(date)}
      period={{ label: 'Prop board date', previous: nbaBoardPath(previousDate, market), next: nbaBoardPath(nextDate, market) }}
      stats={<section className="page-head__stats" aria-label="Prop board summary">
        <StatChip value={games.length} label="Games" /><StatChip value={rowCount} label="Player-market rows" />
      </section>} />
    <nav className="nfl-prop-pills" aria-label="Prop categories">
      {groups.map(item => <button key={item.market} type="button"
        className={[item.market === market && 'is-selected', item.rows.length === 0 && 'is-empty'].filter(Boolean).join(' ')}
        aria-pressed={item.market === market} onClick={() => selectMarket(item.market)}>
        {nbaMarketLabel(item.market)}<em>{item.rows.length}</em>
      </button>)}
    </nav>
    <p className="nba-prop-board__legend">Reference only. Rows follow tip time, then player name. Gaps are projection minus line; P(over) is served for eligible assists lines. No picks or ranking. Dates follow the Eastern game calendar; tip times are CT.</p>
    {games.length === 0 ? <div className="nfl-empty">No NBA games on this date.</div>
      : rowCount === 0 ? <div className="nfl-empty">NBA games are scheduled on this date, but no prop lines are available.</div>
        : <NbaPropBoardMarket key={`${requested}:${date}:${market}`} group={group} modelVersion={modelVersion} />}
  </div></div>
}
