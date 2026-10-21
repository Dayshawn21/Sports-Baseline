import { Drawer } from 'antd'
import { useEffect, useMemo, useState } from 'react'
import { MarketPills, PropBoardFilters, PropBoardHead } from '~/components/tennis/TennisPropBoardControls'
import TennisPropEvidencePanel from '~/components/tennis/TennisPropEvidencePanel'
import { TennisPropTable } from '~/components/tennis/TennisPropTable'
import ErrorState from '~/components/shared/ErrorState'
import LoadingState from '~/components/shared/LoadingState'
import { useIsMobile } from '~/hooks/useIsMobile'
import { useTennisToday } from '~/hooks/useTennisToday'
import { useBestPicks } from '~/hooks/useBestPicks'
import { useBetProps, useDKProps, usePrizePicksProps } from '~/hooks/useProps'
import { buildTennisPropBoard, moneylineBoardRows, winASetBoardRows, type TennisPropSource, type TennisTourFilter } from '~/utils/tennisPropBoard'
import './tennis-prop-board.css'
import './tennis-prop-board-filters.css'

export default function TennisPropBoardPage() {
  const [source, setSource] = useState<TennisPropSource>('all')
  const [tour, setTour] = useState<TennisTourFilter>('all')
  const [market, setMarket] = useState<string | null>(null)
  const [showAll, setShowAll] = useState(false)
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const isMobile = useIsMobile()
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
  const selected = rows.find(row => row.id === selectedId) ?? null
  const loading = prizePicks.isLoading || draftKings.isLoading || betOnline.isLoading || predictions.isLoading || bestPicks.isLoading
  const allFailed = prizePicks.isError && draftKings.isError && betOnline.isError

  useEffect(() => { setMarket(null) }, [source, tour])
  useEffect(() => { setSelectedId(null) }, [source, tour, market, showAll])
  if (loading) return <LoadingState message="Loading current tennis prop board..." />
  if (allFailed) return <ErrorState error={prizePicks.error ?? draftKings.error ?? betOnline.error} onRetry={() => { void prizePicks.refetch(); void draftKings.refetch(); void betOnline.refetch() }} />

  return <div className="page-shell tennis-prop-board"><div className="page-container is-wide">
    <PropBoardHead lines={visibleLineCount} rateable={rateableCount} markets={categories.length} />
    {(prizePicks.isError || draftKings.isError || betOnline.isError || predictions.isError || bestPicks.isError) && <div className="tennis-prop-notice" role="status">Some data could not be loaded. Available current lines are still shown.</div>}
    {category && <MarketPills categories={categories} selected={category.market} onSelect={setMarket} />}
    <PropBoardFilters source={source} tour={tour} showAll={showAll} onSource={setSource} onTour={setTour} onShowAll={setShowAll} />
    {category ? <section className="prop-table-panel" aria-label={`${category.label} prop lines`}>
      <div className="tennis-prop-availability">
        <p role="status">Ranked lines: {category.rateable.length}. Reference lines: {category.other.length}{category.other.length > 0 ? showAll ? ' (shown).' : ' (hidden).' : '.'}</p>
        {category.other.length > 0 && <button type="button" className="tennis-prop-text-action" aria-expanded={showAll} aria-controls="tennis-prop-lines" onClick={() => setShowAll(!showAll)}>{showAll ? 'Hide reference lines' : 'Show reference lines'} ({category.other.length})</button>}
      </div>
      <p className="tennis-prop-evidence-hint">View evidence for recent matches, projection inputs, and quality notes.</p>
      <TennisPropTable category={category} selectedId={selected?.id ?? null} onOpen={row => setSelectedId(row.id)}
        rateable={category.rateable.map((row, index) => ({ row, rank: index + 1 }))}
        other={showAll ? category.other.map(row => ({ row, rank: null })) : []} />
    </section> : <div className="tennis-prop-empty-state">No tennis prop lines are available for these filters. Try a different source or tour.</div>}
    <Drawer open={selected !== null} onClose={() => setSelectedId(null)} width={isMobile ? '100%' : 460} title={null} aria-label={`Prop evidence for ${selected?.playerName ?? 'selected player'}`} className="tennis-prop-drawer" destroyOnHidden>
      {selected && <TennisPropEvidencePanel row={selected} />}
    </Drawer>
  </div></div>
}
