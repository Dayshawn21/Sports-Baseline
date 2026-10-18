import { Drawer } from 'antd'
import { useEffect, useMemo, useState } from 'react'
import NflEvidencePanel from '~/components/NflEvidencePanel'
import { NflMarketPills, NflPropBoardFilters, NflPropBoardHead } from '~/components/nfl/NflPropBoardControls'
import { NflPropTable } from '~/components/nfl/NflPropTable'
import ErrorState from '~/components/shared/ErrorState'
import LoadingState from '~/components/shared/LoadingState'
import { useIsMobile } from '~/hooks/useIsMobile'
import { useNflCurrentWeek, useNflSlate } from '~/hooks/useNfl'
import { marketLabel } from '~/utils/nflLabels'
import type { NflPositionFilter } from '~/utils/nflPositions'
import { buildNflPropBoard, filterNflPropBoardGames, flattenSlateLines } from '~/utils/nflPropBoard'
import { groupNflPropRows } from '~/utils/nflPropRows'
import './nfl-slate.css'
import './nfl-prop-board.css'

export default function NflPropBoardPage() {
  // Null follows the current week; a user's pick pins it.
  const [season, setSeason] = useState<number | null>(null)
  const [week, setWeek] = useState<number | null>(null)
  const [position, setPosition] = useState<NflPositionFilter>('all')
  const [market, setMarket] = useState<string | null>(null)
  const [gameFilter, setGameFilter] = useState('all')
  const [showAll, setShowAll] = useState(false)
  const [selectedLineId, setSelectedLineId] = useState<number | null>(null)
  const isMobile = useIsMobile()
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
  const selectedLine = boardLines.find(row => row.lineId === selectedLineId) ?? null
  const selectedGame = availableGames.find(game => game.gameId === selectedLine?.gameId) ?? null
  // A position or week change can empty the chosen market, so fall back rather than show nothing.
  useEffect(() => { setMarket(null) }, [activeSeason, activeWeek, position])
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
      <main className="prop-table-panel">
        {category.rateable.length === 0 && <p className="nfl-prop-table-empty">No rateable {marketLabel(category.market).toLowerCase()} lines this week.</p>}
        <NflPropTable category={category} now={Date.now()} selectedLineId={selectedLine?.lineId ?? null} onOpen={row => setSelectedLineId(row.lineId)}
          rateable={category.rateable.map((row, index) => ({ row, rank: index + 1 }))}
          other={showAll ? category.other.map(row => ({ row, rank: null })) : []} />
      </main>
      <Drawer open={selectedLine !== null} onClose={() => setSelectedLineId(null)} width={isMobile ? '100%' : 460} title={null} className="nfl-slate nfl-game nfl-game-drawer" destroyOnHidden>
        {selectedLine && <NflEvidencePanel row={selectedLine} game={selectedGame} alternates={alternates.get(selectedLine.lineId) ?? []} />}
      </Drawer>
    </> : <div className="nfl-empty">No upcoming prop lines for this season and week.</div>}
  </div></div>
}
