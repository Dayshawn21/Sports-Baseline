import { useEffect, useMemo, useState } from 'react'
import { MarketPills, PropBoardFilters, PropBoardHead } from '~/components/tennis/TennisPropBoardControls'
import { TennisPropTable } from '~/components/tennis/TennisPropTable'
import ErrorState from '~/components/shared/ErrorState'
import LoadingState from '~/components/shared/LoadingState'
import { useTennisToday } from '~/hooks/useTennisToday'
import { useBestPicks } from '~/hooks/useBestPicks'
import { useDKProps, usePrizePicksProps } from '~/hooks/useProps'
import { propPlayerPath } from '~/utils/tennisPlayerProps'
import { buildTennisPropBoard, moneylineBoardRows, winASetBoardRows, type TennisPropSource, type TennisTourFilter } from '~/utils/tennisPropBoard'
import './tennis-prop-board.css'
import './tennis-prop-board-filters.css'

export default function TennisPropBoardPage() {
  const [source, setSource] = useState<TennisPropSource>('all')
  const [tour, setTour] = useState<TennisTourFilter>('all')
  const [market, setMarket] = useState<string | null>(null)
  const [showAll, setShowAll] = useState(false)
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
  const categories = useMemo(() => buildTennisPropBoard(props, predictions.data?.matches ?? [], source, tour), [props, predictions.data, source, tour])
  const visibleLineCount = useMemo(() => categories.reduce((total, category) => total + category.rateable.length + category.other.length, 0), [categories])
  const rateableCount = useMemo(() => categories.reduce((total, category) => total + category.rateable.length, 0), [categories])
  const category = categories.find(item => item.market === market) ?? categories.find(item => item.rateable.length > 0) ?? categories[0] ?? null
  const loading = prizePicks.isLoading || draftKings.isLoading || predictions.isLoading || bestPicks.isLoading
  const allFailed = prizePicks.isError && draftKings.isError

  useEffect(() => { setMarket(null) }, [source, tour])
  if (loading) return <LoadingState message="Loading current tennis prop board..." />
  if (allFailed) return <ErrorState error={prizePicks.error ?? draftKings.error} onRetry={() => { void prizePicks.refetch(); void draftKings.refetch() }} />

  return <div className="page-shell tennis-prop-board"><div className="page-container is-wide">
    <PropBoardHead lines={visibleLineCount} rateable={rateableCount} markets={categories.length} />
    {(prizePicks.isError || draftKings.isError || predictions.isError || bestPicks.isError) && <div className="tennis-prop-notice" role="status">Some data could not be loaded. Available current lines are still shown.</div>}
    {category && <MarketPills categories={categories} selected={category.market} onSelect={setMarket} />}
    <PropBoardFilters source={source} tour={tour} showAll={showAll} onSource={setSource} onTour={setTour} onShowAll={setShowAll} />
    {category ? <section className="prop-table-panel" aria-label={`${category.label} prop lines`}>
      <div className="tennis-prop-availability">
        <p role="status">Rated lines: {category.rateable.length}. Lines for review: {category.other.length}{category.other.length > 0 ? showAll ? ' (shown).' : ' (hidden).' : '.'}</p>
        {category.other.length > 0 && <button type="button" className="tennis-prop-text-action" aria-expanded={showAll} aria-controls="tennis-prop-lines" onClick={() => setShowAll(!showAll)}>{showAll ? 'Hide lines for review' : 'Show lines for review'} ({category.other.length})</button>}
      </div>
      <p className="tennis-prop-evidence-hint">Open a row for the player's recent matches, projection inputs, and quality notes.</p>
      <TennisPropTable category={category} pathFor={row => propPlayerPath(row, predictions.data?.matches ?? [])} from="/tennis/board"
        rateable={category.rateable.map(row => ({ row, rated: true }))}
        other={showAll ? category.other.map(row => ({ row, rated: false })) : []} />
    </section> : <div className="tennis-prop-empty-state">No tennis prop lines are available for these filters. Try a different source or tour.</div>}
  </div></div>
}
