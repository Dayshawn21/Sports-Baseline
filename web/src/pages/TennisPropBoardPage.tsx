import { useEffect, useMemo, useRef, useState } from 'react'
import { MarketPills, PropBoardFilters, PropBoardHead } from '~/components/tennis/TennisPropBoardControls'
import { TennisPropCardGrid } from '~/components/tennis/TennisPropCard'
import TennisPropEvidencePanel from '~/components/tennis/TennisPropEvidencePanel'
import ErrorState from '~/components/shared/ErrorState'
import LoadingState from '~/components/shared/LoadingState'
import { useTennisToday } from '~/hooks/useTennisToday'
import { useBestPicks } from '~/hooks/useBestPicks'
import { useBetProps, useDKProps, usePrizePicksProps } from '~/hooks/useProps'
import { buildTennisPropBoard, moneylineBoardRows, winASetBoardRows, type TennisBoardLine, type TennisPropSource, type TennisTourFilter } from '~/utils/tennisPropBoard'
import './tennis-prop-board.css'
import './tennis-prop-board-filters.css'

// Matches the tennis-prop-board.css breakpoint where the panel stacks under the grid.
const STACKED_QUERY = '(max-width: 860px)'

export default function TennisPropBoardPage() {
  const [source, setSource] = useState<TennisPropSource>('all')
  const [tour, setTour] = useState<TennisTourFilter>('all')
  const [market, setMarket] = useState<string | null>(null)
  const [showAll, setShowAll] = useState(false)
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const panelRef = useRef<HTMLElement>(null)
  const predictions = useTennisToday()
  const bestPicks = useBestPicks()
  const prizePicks = usePrizePicksProps()
  const draftKings = useDKProps()
  const betOnline = useBetProps()
  const props = useMemo(() => [
    ...(prizePicks.data?.props ?? []),
    ...(draftKings.data?.props ?? []),
    ...(betOnline.data?.props ?? []),
    ...moneylineBoardRows(predictions.data?.matches ?? []),
    ...winASetBoardRows(bestPicks.data?.matches ?? []),
  ], [prizePicks.data, draftKings.data, betOnline.data, predictions.data, bestPicks.data])
  const categories = useMemo(() => buildTennisPropBoard(props, predictions.data?.matches ?? [], source, tour), [props, predictions.data, source, tour])
  const visibleLineCount = useMemo(() => categories.reduce((total, category) => total + category.rateable.length + category.other.length, 0), [categories])
  const rateableCount = useMemo(() => categories.reduce((total, category) => total + category.rateable.length, 0), [categories])
  const category = categories.find(item => item.market === market) ?? categories.find(item => item.rateable.length > 0) ?? categories[0] ?? null
  const rows = category ? [...category.rateable, ...(showAll ? category.other : [])] : []
  const selected = rows.find(row => row.id === selectedId) ?? rows[0] ?? null
  const loading = prizePicks.isLoading || draftKings.isLoading || betOnline.isLoading || predictions.isLoading || bestPicks.isLoading
  const allFailed = prizePicks.isError && draftKings.isError && betOnline.isError

  useEffect(() => { setMarket(null); setSelectedId(null) }, [source, tour])
  function selectLine(row: TennisBoardLine) {
    setSelectedId(row.id)
    // Stacked, the panel sits below the whole grid, so bring it to the reader.
    if (window.matchMedia(STACKED_QUERY).matches) {
      requestAnimationFrame(() => panelRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }))
    }
  }
  if (loading) return <LoadingState message="Loading current tennis prop board..." />
  if (allFailed) return <ErrorState error={prizePicks.error ?? draftKings.error ?? betOnline.error} onRetry={() => { void prizePicks.refetch(); void draftKings.refetch(); void betOnline.refetch() }} />

  return <div className="page-shell tennis-prop-board"><div className="page-container is-wide">
    <PropBoardHead lines={visibleLineCount} rateable={rateableCount} markets={categories.length} />
    {(prizePicks.isError || draftKings.isError || betOnline.isError || predictions.isError || bestPicks.isError) && <div className="tennis-prop-notice" role="status">Some data could not be loaded. Available current lines are still shown.</div>}
    {category && <MarketPills categories={categories} selected={category.market} onSelect={setMarket} />}
    <PropBoardFilters source={source} tour={tour} showAll={showAll} onSource={setSource} onTour={setTour} onShowAll={setShowAll} />
    {category ? <main className="tennis-prop-layout"><TennisPropCardGrid category={category} showAll={showAll} selectedId={selected?.id ?? null} onOpen={selectLine} />{selected && <TennisPropEvidencePanel ref={panelRef} row={selected} />}</main> : <div className="tennis-prop-empty-state">No current tennis prop lines are loaded for this source. Try another provider or run the prop ingest.</div>}
  </div></div>
}
