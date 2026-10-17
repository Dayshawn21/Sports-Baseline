import { useEffect, useMemo, useRef, useState } from 'react'
import NflEvidencePanel from '~/components/NflEvidencePanel'
import { NflMarketPills, NflPropBoardFilters, NflPropBoardHead } from '~/components/nfl/NflPropBoardControls'
import { NflPropCardGrid } from '~/components/nfl/NflPropCard'
import ErrorState from '~/components/shared/ErrorState'
import LoadingState from '~/components/shared/LoadingState'
import { useNflCurrentWeek, useNflSlate } from '~/hooks/useNfl'
import type { NflPositionFilter } from '~/utils/nflPositions'
import { buildNflPropBoard, filterNflPropBoardGames, flattenSlateLines, type NflBoardLine } from '~/utils/nflPropBoard'
import { groupNflPropRows } from '~/utils/nflPropRows'
import './nfl-slate.css'
import './nfl-prop-board.css'

const STACKED_QUERY = '(max-width: 860px)'

export default function NflPropBoardPage() {
  // Null follows the current week; a user's pick pins it.
  const [season, setSeason] = useState<number | null>(null)
  const [week, setWeek] = useState<number | null>(null)
  const [position, setPosition] = useState<NflPositionFilter>('all')
  const [market, setMarket] = useState<string | null>(null)
  const [gameFilter, setGameFilter] = useState('all')
  const [showAll, setShowAll] = useState(false)
  const [selectedLineId, setSelectedLineId] = useState<number | null>(null)
  const panelRef = useRef<HTMLDivElement>(null)
  const currentWeek = useNflCurrentWeek()
  const activeSeason = season ?? currentWeek.data?.season ?? null
  const activeWeek = week ?? currentWeek.data?.week ?? null
  const slate = useNflSlate(activeSeason, activeWeek)
  const availableGames = useMemo(() => filterNflPropBoardGames(slate.data?.games ?? [], null), [slate.data])
  const selectedGameId = gameFilter === 'all' ? null : Number(gameFilter)
  const filteredGames = useMemo(() => filterNflPropBoardGames(availableGames, selectedGameId), [availableGames, selectedGameId])
  const categories = useMemo(() => buildNflPropBoard(filteredGames, position), [filteredGames, position])
  const alternates = useMemo(() => new Map(groupNflPropRows(flattenSlateLines(filteredGames)).map(item => [item.primary.lineId, item.alternates])), [filteredGames])
  const category = categories.find(item => item.market === market)
    ?? categories.find(item => item.rateable.length > 0)
    ?? categories[0]
    ?? null
  const boardLines = category ? [...category.rateable, ...(showAll ? category.other : [])] : []
  const selectedLine = boardLines.find(row => row.lineId === selectedLineId) ?? boardLines[0] ?? null
  const selectedGame = availableGames.find(game => game.gameId === selectedLine?.gameId) ?? null
  // A position or week change can empty the chosen market, so fall back rather than show nothing.
  useEffect(() => { setMarket(null) }, [activeSeason, activeWeek, position])
  function selectLine(row: NflBoardLine) {
    setSelectedLineId(row.lineId)
    // Stacked, the panel sits below the whole grid, so bring it to the reader.
    if (window.matchMedia(STACKED_QUERY).matches) {
      requestAnimationFrame(() => panelRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }))
    }
  }
  if (currentWeek.isError && (season === null || week === null)) return <ErrorState error={currentWeek.error} onRetry={() => currentWeek.refetch()} />
  if (activeSeason === null || activeWeek === null || slate.isLoading) return <LoadingState message="Loading NFL prop board..." />
  if (slate.isError) return <ErrorState error={slate.error} onRetry={() => slate.refetch()} />
  return <div className="page-shell nfl-slate nfl-prop-board"><div className="page-container is-wide">
    <NflPropBoardHead season={activeSeason} week={activeWeek} games={availableGames.length} categories={categories}
      onSeason={value => { setSeason(value); setWeek(activeWeek); setGameFilter('all') }}
      onWeek={value => { setSeason(activeSeason); setWeek(value); setGameFilter('all') }} />
    {category ? <>
      <NflMarketPills categories={categories} selected={category.market} onSelect={setMarket} />
      <NflPropBoardFilters position={position} gameFilter={gameFilter} games={availableGames} showAll={showAll}
        onPosition={setPosition} onGame={setGameFilter} onShowAll={setShowAll} />
      <main className="nfl-prop-layout">
        <NflPropCardGrid category={category} showAll={showAll} selectedLineId={selectedLine?.lineId ?? null} onOpen={selectLine} />
        {selectedLine && <div className="nfl-prop-layout__panel" ref={panelRef}><NflEvidencePanel row={selectedLine} game={selectedGame} alternates={alternates.get(selectedLine.lineId) ?? []} /></div>}
      </main>
    </> : <div className="nfl-empty">No upcoming prop lines for this season and week.</div>}
  </div></div>
}
