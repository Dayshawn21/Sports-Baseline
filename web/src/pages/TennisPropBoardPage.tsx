import { useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { MarketPills, PropBoardFilters, PropBoardHead } from '~/components/tennis/TennisPropBoardControls'
import { TennisPropTable } from '~/components/tennis/TennisPropTable'
import BoardRecordStrip from '~/components/shared/BoardRecordStrip'
import ErrorState from '~/components/shared/ErrorState'
import TableSkeleton from '~/components/shared/TableSkeleton'
import { useTennisToday } from '~/hooks/useTennisToday'
import { useBestPicks } from '~/hooks/useBestPicks'
import { useModelPropTiers } from '~/hooks/useModelTrackRecord'
import { useDKProps, usePrizePicksProps } from '~/hooks/useProps'
import { recordStatus, tennisBoardRecord } from '~/utils/boardRecord'
import { parsePlayerFilter, visibleMarket, withPropListFilters } from '~/utils/propFilters'
import { propPlayerPath } from '~/utils/tennisPlayerProps'
import { buildTennisPropBoard, filterTennisBoardCategories, lineTypeApplies, moneylineBoardRows, parseTennisContextFilter, tennisBoardPath, tennisPlayerOptions, winASetBoardRows, withTennisContextFilter, type TennisPropSource } from '~/utils/tennisPropBoard'
import './tennis-prop-board.css'
import './tennis-prop-board-filters.css'

export default function TennisPropBoardPage() {
  const [source, setSource] = useState<TennisPropSource>('all')
  const [market, setMarket] = useState<string | null>(null)
  const [showAll, setShowAll] = useState(false)
  const [params, setParams] = useSearchParams()
  const filter = useMemo(() => parseTennisContextFilter(params), [params])
  const effectiveFilter = useMemo(() => lineTypeApplies(source) ? filter : { ...filter, lineType: 'default' as const }, [filter, source])
  const predictions = useTennisToday()
  const bestPicks = useBestPicks()
  const prizePicks = usePrizePicksProps()
  const draftKings = useDKProps()
  const props = useMemo(() => [
    ...(prizePicks.data?.props ?? []),
    ...(draftKings.data?.props ?? []),
    ...moneylineBoardRows(predictions.data?.matches ?? []),
    ...winASetBoardRows(bestPicks.data?.matches ?? []),
  ], [prizePicks.data, draftKings.data, predictions.data, bestPicks.data])
  const categories = useMemo(() => buildTennisPropBoard(props, predictions.data?.matches ?? [], source, effectiveFilter), [props, predictions.data, source, effectiveFilter])
  const players = useMemo(() => parsePlayerFilter(params), [params])
  const filtered = useMemo(() => filterTennisBoardCategories(categories, players), [categories, players])
  const playerNames = useMemo(() => tennisPlayerOptions(categories, players), [categories, players])
  const filtering = players.length > 0
  const chosen = categories.find(item => item.market === market) ?? categories.find(item => item.rateable.length > 0) ?? categories[0] ?? null
  const shownMarket = visibleMarket(chosen?.market ?? null, filtered.map(item => ({ market: item.market, count: item.rateable.length + item.other.length })), filtering)
  const category = filtered.find(item => item.market === shownMarket) ?? null
  const noMatches = filtering && filtered.every(item => item.rateable.length + item.other.length === 0)
  const loading = prizePicks.isLoading || draftKings.isLoading || predictions.isLoading || bestPicks.isLoading
  const allFailed = prizePicks.isError && draftKings.isError
  const propTiers = useModelPropTiers()
  const record = tennisBoardRecord(propTiers.data, recordStatus(propTiers))

  const filterKey = withTennisContextFilter(new URLSearchParams(), effectiveFilter).toString()
  useEffect(() => { setMarket(null) }, [source, filterKey])
  if (loading) return <div className="page-shell tennis-prop-board"><div className="page-container is-wide">
    <TableSkeleton label="Loading current tennis prop board..." columns={7} rows={5} rowHeight={108} stackedRowHeight={278} variant="board" />
  </div></div>
  if (allFailed) return <ErrorState error={prizePicks.error ?? draftKings.error} onRetry={() => { void prizePicks.refetch(); void draftKings.refetch() }} />

  return <div className="page-shell tennis-prop-board"><div className="page-container is-wide">
    <PropBoardHead />
    <BoardRecordStrip record={record} />
    {(prizePicks.isError || draftKings.isError || predictions.isError || bestPicks.isError) && <div className="tennis-prop-notice" role="status">Some data could not be loaded. Available current lines are still shown.</div>}
    {category && <MarketPills categories={filtered} selected={category.market} onSelect={setMarket} />}
    <PropBoardFilters source={source} filter={filter} showAll={showAll} players={players} playerNames={playerNames} onSource={setSource}
      onFilter={value => setParams(withTennisContextFilter(params, value), { replace: true })} onShowAll={setShowAll}
      onPlayers={value => setParams(withPropListFilters(params, { player: value }), { replace: true })} />
    {noMatches ? <div className="tennis-prop-empty-state">No lines for these players. Try a different source, tour, surface, format or line type.</div> : category ? <section className="prop-table-panel" aria-label={`${category.label} prop lines`}>
      <div className="tennis-prop-availability">
        <p role="status">Rated lines: {category.rateable.length}. Lines for review: {category.other.length}{category.other.length > 0 ? showAll ? ' (shown).' : ' (hidden).' : '.'}</p>
        {category.other.length > 0 && <button type="button" className="tennis-prop-text-action" aria-expanded={showAll} aria-controls="tennis-prop-lines" onClick={() => setShowAll(!showAll)}>{showAll ? 'Hide lines for review' : 'Show lines for review'} ({category.other.length})</button>}
      </div>
      <p className="tennis-prop-evidence-hint">Open a row for the player's recent matches, projection inputs, and quality notes.</p>
      <TennisPropTable category={category} pathFor={row => propPlayerPath(row, predictions.data?.matches ?? [])} from={tennisBoardPath(players, effectiveFilter)}
        rateable={category.rateable.map(row => ({ row, rated: true }))}
        other={showAll ? category.other.map(row => ({ row, rated: false })) : []} />
    </section> : <div className="tennis-prop-empty-state">No tennis prop lines are available for these filters. Try a different source, tour, surface, format or line type.</div>}
  </div></div>
}
