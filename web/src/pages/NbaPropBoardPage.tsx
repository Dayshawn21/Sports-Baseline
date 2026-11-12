import { Select } from 'antd'
import { useMemo } from 'react'
import { useSearchParams } from 'react-router-dom'
import NbaPropBoardMarket from '~/components/nba/NbaPropBoardMarket'
import { NbaSlateDigest } from '~/components/nba/NbaSlateDigest'
import BoardFilterBar from '~/components/shared/BoardFilterBar'
import BoardRecordStrip from '~/components/shared/BoardRecordStrip'
import ErrorState from '~/components/shared/ErrorState'
import LoadingState from '~/components/shared/LoadingState'
import PageHead from '~/components/shared/PageHead'
import StatChip from '~/components/shared/StatChip'
import { useBoardFilters } from '~/hooks/useBoardFilters'
import { useNbaModelRanking, useNbaPropBoard, useNbaSlateGaps } from '~/hooks/useNba'
import { rankingBoardRecord, recordStatus } from '~/utils/boardRecord'
import { nbaMarketLabel } from '~/utils/nbaLineOnly'
import { nbaBoardMarket, nbaBoardPath, nbaPropBoard } from '~/utils/nbaPropBoard'
import { nbaSlateDigest, parseSlateDate, slateDateLabel } from '~/utils/nbaSlate'
import { activeOutFilter, filterTeammateOut, parseOutFilter, teammateOutOptions, type NbaTeammateOutOption } from '~/utils/nbaTeammateOut'
import { boardPlayerOptions, filterBoardMarkets, isFiltering, visibleMarket } from '~/utils/propFilters'
import './nfl-slate.css'
import './nfl-prop-board.css'
import './nba-prop-board.css'

export default function NbaPropBoardPage() {
  const [params, setParams] = useSearchParams()
  const requested = parseSlateDate(params.get('date'))
  const board = useNbaPropBoard(requested)
  const groups = useMemo(() => nbaPropBoard(board.data?.games ?? []), [board.data])
  const market = nbaBoardMarket(params.get('market'), groups)
  const games = board.data?.games
  const { filter, teams, onPlayers, onTeam, onGames } = useBoardFilters(games)
  const outOptions = useMemo(() => teammateOutOptions(games ?? []), [games])
  const out = activeOutFilter(parseOutFilter(params), outOptions)
  const filtered = useMemo(() => filterTeammateOut(filterBoardMarkets(groups, filter), out), [groups, filter, out])
  const players = useMemo(() => boardPlayerOptions(filterTeammateOut(groups, out), filter), [groups, filter, out])
  const shownMarket = visibleMarket(market, filtered.map(item => ({ market: item.market, count: item.rows.length })), isFiltering(filter) || out !== null)
  const group = filtered.find(item => item.market === shownMarket)!
  const rowCount = groups.reduce((sum, item) => sum + item.rows.length, 0)
  const filteredCount = filtered.reduce((sum, item) => sum + item.rows.length, 0)
  // The slate's own digest request, so both strips always agree.
  const gaps = useNbaSlateGaps(board.data?.date ?? null)
  const digest = useMemo(() => nbaSlateDigest(gaps.data?.items ?? []), [gaps.data])
  const ranking = useNbaModelRanking()
  const record = rankingBoardRecord('nba', ranking.data, recordStatus(ranking))
  if (board.isLoading) return <LoadingState message="Loading NBA prop board..." />
  if (board.isError || !board.data) return <ErrorState error={board.error} onRetry={() => void board.refetch()} />
  const { date, previousDate, nextDate } = board.data
  const gameCount = board.data.games.length
  const selectOut = (value: string | undefined) => {
    const next = new URLSearchParams(params)
    if (value === undefined) next.delete('out')
    else next.set('out', value)
    setParams(next, { replace: true })
  }
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
        <StatChip value={gameCount} label="Games" /><StatChip value={rowCount} label="Player-market rows" />
      </section>} />
    <BoardRecordStrip record={record} />
    <NbaSlateDigest items={digest} />
    <nav className="nfl-prop-pills" aria-label="Prop categories">
      {filtered.map(item => <button key={item.market} type="button"
        className={[item.market === shownMarket && 'is-selected', item.rows.length === 0 && 'is-empty'].filter(Boolean).join(' ')}
        aria-pressed={item.market === shownMarket} onClick={() => selectMarket(item.market)}>
        {nbaMarketLabel(item.market)}<em>{item.rows.length}</em>
      </button>)}
    </nav>
    {rowCount > 0 && <BoardFilterBar games={board.data.games} teams={teams} playerNames={players} filter={filter} onPlayers={onPlayers} onTeam={onTeam} onGames={onGames}>
      <Select aria-label="Teammate out" allowClear showSearch optionFilterProp="label" value={out?.id} onChange={selectOut} disabled={outOptions.length === 0}
        placeholder={outOptions.length === 0 ? 'No players listed out' : 'Teammate out'}
        options={outOptions.map(option => ({ value: option.id, label: outLabel(option) }))} />
    </BoardFilterBar>}
    <p className="nba-prop-board__legend">Reference only, no picks. The strip above lists the day's largest gaps; rows below follow tip time, then player name, and are not ranked. Gaps are projection minus line; P(over) is served for eligible assists lines. Dates follow the Eastern game calendar; tip times are CT.</p>
    {gameCount === 0 ? <div className="nfl-empty">No NBA games on this date.</div>
      : rowCount === 0 ? <div className="nfl-empty">NBA games are scheduled on this date, but no prop lines are available.</div>
        : filteredCount === 0 ? <div className="nfl-empty">No lines match these filters. Clear the search or choose another team, game or teammate out.</div>
          : <NbaPropBoardMarket key={`${requested}:${date}:${shownMarket}`} group={group} date={date} />}
  </div></div>
}

function outLabel(option: NbaTeammateOutOption): string {
  return `${option.playerName} (${option.team}, ${option.status}${option.stale ? ', stale report' : ''})`
}
