import { Select } from 'antd'
import { useMemo } from 'react'
import { useSearchParams } from 'react-router-dom'
import NhlPropBoardMarket from '~/components/nhl/NhlPropBoardMarket'
import BoardFilterBar from '~/components/shared/BoardFilterBar'
import BoardRecordStrip from '~/components/shared/BoardRecordStrip'
import ErrorState from '~/components/shared/ErrorState'
import TableSkeleton from '~/components/shared/TableSkeleton'
import PageHead from '~/components/shared/PageHead'
import StatChip from '~/components/shared/StatChip'
import { useBoardFilters } from '~/hooks/useBoardFilters'
import { useNhlModelRanking, useNhlPropBoard, useNhlSlate } from '~/hooks/useNhl'
import { rankingBoardRecord, recordStatus } from '~/utils/boardRecord'
import { filterStartingGoalie, goalieSides, NHL_GOALIE_FILTERS, parseGoalieFilter, type NhlGoalieFilter } from '~/utils/nhlGoalieFilter'
import { nhlMarketLabel } from '~/utils/nhlLineOnly'
import { nhlBoardMarket, nhlBoardPath, nhlPropBoard } from '~/utils/nhlPropBoard'
import { parseSlateDate, slateDateLabel } from '~/utils/nhlSlate'
import { boardPlayerOptions, filterBoardMarkets, isFiltering, visibleMarket } from '~/utils/propFilters'
import './nfl-slate.css'
import './nfl-prop-board.css'
import './nhl-prop-board.css'

export default function NhlPropBoardPage() {
  const [params, setParams] = useSearchParams()
  const requested = parseSlateDate(params.get('date'))
  const board = useNhlPropBoard(requested)
  const groups = useMemo(() => nhlPropBoard(board.data?.games ?? []), [board.data])
  const market = nhlBoardMarket(params.get('market'), groups)
  const { filter, teams, onPlayers, onTeam, onGames } = useBoardFilters(board.data?.games)
  const slate = useNhlSlate(board.data?.date ?? null, board.data !== undefined)
  const sides = useMemo(() => goalieSides(slate.data?.games ?? [], new Date()), [slate.data])
  // Without the slate there is nothing to judge a starter by, so the filter waits rather than emptying the board.
  const goalie: NhlGoalieFilter = slate.data ? parseGoalieFilter(params) : 'any'
  const filtered = useMemo(() => filterStartingGoalie(filterBoardMarkets(groups, filter), goalie, sides), [groups, filter, goalie, sides])
  const players = useMemo(() => boardPlayerOptions(filterStartingGoalie(groups, goalie, sides), filter), [groups, filter, goalie, sides])
  const shownMarket = visibleMarket(market, filtered.map(item => ({ market: item.market, count: item.rows.length })), isFiltering(filter) || goalie !== 'any')
  const group = filtered.find(item => item.market === shownMarket)!
  const rowCount = groups.reduce((sum, item) => sum + item.rows.length, 0)
  const filteredCount = filtered.reduce((sum, item) => sum + item.rows.length, 0)
  const ranking = useNhlModelRanking()
  const record = rankingBoardRecord('nhl', ranking.data, recordStatus(ranking))
  if (board.isLoading) return <div className="page-shell nfl-slate nhl-prop-board"><div className="page-container is-wide">
    <TableSkeleton label="Loading NHL prop board..." columns={8} rowHeight={58} stackedRowHeight={76} variant="board" />
  </div></div>
  if (board.isError || !board.data) return <ErrorState error={board.error} onRetry={() => void board.refetch()} />
  const { date, previousDate, nextDate, games } = board.data
  const selectGoalie = (value: NhlGoalieFilter) => {
    const next = new URLSearchParams(params)
    if (value === 'any') next.delete('goalie')
    else next.set('goalie', value)
    setParams(next, { replace: true })
  }
  const goalieWaiting = slate.isError ? 'Goalie reports unavailable' : slate.data ? null : 'Goalie reports loading'
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
    <BoardRecordStrip record={record} />
    <nav className="nfl-prop-pills" aria-label="Prop categories">
      {filtered.map(item => <button key={item.market} type="button"
        className={[item.market === shownMarket && 'is-selected', item.rows.length === 0 && 'is-empty'].filter(Boolean).join(' ')}
        aria-pressed={item.market === shownMarket} onClick={() => selectMarket(item.market)}>
        {nhlMarketLabel(item.market)}<em>{item.rows.length}</em>
      </button>)}
    </nav>
    {rowCount > 0 && <BoardFilterBar games={games} teams={teams} playerNames={players} filter={filter} onPlayers={onPlayers} onTeam={onTeam} onGames={onGames}>
      <Select aria-label="Starting goalie" value={goalieWaiting ? undefined : goalie} onChange={selectGoalie} disabled={goalieWaiting !== null}
        placeholder={goalieWaiting ?? 'Starting goalie'}
        options={NHL_GOALIE_FILTERS.map(option => ({ value: option.value, label: option.value === 'any' ? 'Any starting goalie' : `Starting goalie: ${option.label}` }))} />
    </BoardFilterBar>}
    <p className="nhl-prop-board__legend">Reference only, no picks. Stored PrizePicks full-game lines beside a 20-game average projection and its gap to the standard line (projection minus line). A goalie shows a projection only for a confirmed or expected starter. Rows follow puck drop, then player name, and are not ranked. Dates follow the Eastern game calendar; puck drop is CT.</p>
    {games.length === 0 ? <div className="nfl-empty">No NHL games on this date.</div>
      : rowCount === 0 ? <div className="nfl-empty">NHL games are scheduled on this date, but no prop lines are available.</div>
        : filteredCount === 0 ? <div className="nfl-empty">No lines match these filters. Clear the search or choose another team, game or starting goalie.</div>
          : <NhlPropBoardMarket key={`${requested}:${date}:${shownMarket}`} group={group} date={date} />}
  </div></div>
}
