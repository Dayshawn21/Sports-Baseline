import { useMemo } from 'react'
import { useSearchParams } from 'react-router-dom'
import NhlPropBoardMarket from '~/components/nhl/NhlPropBoardMarket'
import BoardFilterBar from '~/components/shared/BoardFilterBar'
import ErrorState from '~/components/shared/ErrorState'
import LoadingState from '~/components/shared/LoadingState'
import PageHead from '~/components/shared/PageHead'
import StatChip from '~/components/shared/StatChip'
import { useBoardFilters } from '~/hooks/useBoardFilters'
import { useNhlPropBoard } from '~/hooks/useNhl'
import { nhlMarketLabel } from '~/utils/nhlLineOnly'
import { nhlBoardMarket, nhlBoardPath, nhlPropBoard } from '~/utils/nhlPropBoard'
import { parseSlateDate, slateDateLabel } from '~/utils/nhlSlate'
import { filterBoardMarkets, isFiltering, visibleMarket } from '~/utils/propFilters'
import './nfl-slate.css'
import './nfl-prop-board.css'
import './nhl-prop-board.css'

export default function NhlPropBoardPage() {
  const [params, setParams] = useSearchParams()
  const requested = parseSlateDate(params.get('date'))
  const board = useNhlPropBoard(requested)
  const groups = useMemo(() => nhlPropBoard(board.data?.games ?? []), [board.data])
  const market = nhlBoardMarket(params.get('market'), groups)
  const { filter, teams, onQuery, onTeam, onGame } = useBoardFilters(board.data?.games)
  const { q, team, game } = filter
  const filtered = useMemo(() => filterBoardMarkets(groups, { q, team, game }), [groups, q, team, game])
  const shownMarket = visibleMarket(market, filtered.map(item => ({ market: item.market, count: item.rows.length })), isFiltering(filter))
  const group = filtered.find(item => item.market === shownMarket)!
  const rowCount = groups.reduce((sum, item) => sum + item.rows.length, 0)
  const filteredCount = filtered.reduce((sum, item) => sum + item.rows.length, 0)
  if (board.isLoading) return <LoadingState message="Loading NHL prop board..." />
  if (board.isError || !board.data) return <ErrorState error={board.error} onRetry={() => void board.refetch()} />
  const { date, previousDate, nextDate, games } = board.data
  const selectMarket = (value: string) => {
    const next = new URLSearchParams(params)
    if (requested === null) next.delete('date')
    next.set('market', value)
    setParams(next)
  }
  return <div className="page-shell nfl-slate nhl-prop-board"><div className="page-container is-wide">
    <PageHead title="NHL props" meta={slateDateLabel(date)}
      period={{ label: 'Prop board date', previous: nhlBoardPath(previousDate, market), next: nhlBoardPath(nextDate, market) }}
      stats={<section className="page-head__stats" aria-label="Prop board summary">
        <StatChip value={games.length} label="Games" /><StatChip value={rowCount} label="Player-market rows" />
      </section>} />
    <nav className="nfl-prop-pills" aria-label="Prop categories">
      {filtered.map(item => <button key={item.market} type="button"
        className={[item.market === shownMarket && 'is-selected', item.rows.length === 0 && 'is-empty'].filter(Boolean).join(' ')}
        aria-pressed={item.market === shownMarket} onClick={() => selectMarket(item.market)}>
        {nhlMarketLabel(item.market)}<em>{item.rows.length}</em>
      </button>)}
    </nav>
    {rowCount > 0 && <BoardFilterBar games={games} teams={teams} filter={filter} onQuery={onQuery} onTeam={onTeam} onGame={onGame} />}
    <p className="nhl-prop-board__legend">Reference only, no picks. Stored PrizePicks full-game lines beside a 20-game average projection and its gap to the standard line (projection minus line). A goalie shows a projection only for a confirmed or expected starter. Rows follow puck drop, then player name, and are not ranked. Dates follow the Eastern game calendar; puck drop is CT.</p>
    {games.length === 0 ? <div className="nfl-empty">No NHL games on this date.</div>
      : rowCount === 0 ? <div className="nfl-empty">NHL games are scheduled on this date, but no prop lines are available.</div>
        : filteredCount === 0 ? <div className="nfl-empty">No lines match these filters. Clear the search or choose another team or game.</div>
          : <NhlPropBoardMarket key={`${requested}:${date}:${shownMarket}`} group={group} date={date} />}
  </div></div>
}
