import { Drawer } from 'antd'
import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import NflEvidencePanel from '~/components/NflEvidencePanel'
import { NflLineOnlyTable } from '~/components/nfl/NflLineOnlyProps'
import { NflMarketPills, NflPropBoardFilters, NflPropBoardHead } from '~/components/nfl/NflPropBoardControls'
import { NflPropTable } from '~/components/nfl/NflPropTable'
import ErrorState from '~/components/shared/ErrorState'
import LoadingState from '~/components/shared/LoadingState'
import { useIsMobile } from '~/hooks/useIsMobile'
import { useNflDrawerFocus } from '~/hooks/useNflDrawerFocus'
import { useNflCurrentWeek, useNflSlate, useNflWeekLineOnlyProps } from '~/hooks/useNfl'
import { formatKickoffTime, marketLabel } from '~/utils/nflLabels'
import type { NflPositionFilter } from '~/utils/nflPositions'
import { buildNflPropBoard, filterNflPropBoardGames, flattenSlateLines } from '~/utils/nflPropBoard'
import { groupNflPropRows } from '~/utils/nflPropRows'
import { isTargetsReference } from '~/utils/nflTargets'
import { availableNflPropGames, nflWeekLineOnlyCategories } from '~/utils/nflWeekLineOnly'
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
  const drawerFocus = useNflDrawerFocus()
  const isMobile = useIsMobile()
  const currentWeek = useNflCurrentWeek()
  const activeSeason = season ?? currentWeek.data?.season ?? null
  const activeWeek = week ?? currentWeek.data?.week ?? null
  const slate = useNflSlate(activeSeason, activeWeek)
  const lineOnly = useNflWeekLineOnlyProps(activeSeason, activeWeek)
  const availableGames = useMemo(() => availableNflPropGames(slate.data?.games ?? [], lineOnly.data?.games ?? []), [slate.data, lineOnly.data])
  const selectedGameId = gameFilter === 'all' ? null : Number(gameFilter)
  const filteredGames = useMemo(() => filterNflPropBoardGames(slate.data?.games ?? [], selectedGameId), [slate.data, selectedGameId])
  const categories = useMemo(() => buildNflPropBoard(filteredGames, position), [filteredGames, position])
  const otherCategories = useMemo(() => nflWeekLineOnlyCategories(lineOnly.data?.games ?? [], position, selectedGameId), [lineOnly.data, position, selectedGameId])
  const pills = [...categories.map(item => ({ market: item.market, count: item.rateable.length })), ...otherCategories.map(item => ({ market: item.market, count: item.count }))]
  const selectedMarket = pills.some(item => item.market === market) ? market
    : categories.find(item => item.rateable.length > 0)?.market ?? pills[0]?.market ?? null
  const alternates = useMemo(() => new Map(groupNflPropRows(flattenSlateLines(filteredGames)).map(item => [item.primary.lineId, item.alternates])), [filteredGames])
  const category = categories.find(item => item.market === selectedMarket) ?? null
  const otherCategory = otherCategories.find(item => item.market === selectedMarket)
  const boardLines = category ? [...category.rateable, ...(showAll ? category.other : [])] : []
  const selectedLine = boardLines.find(row => row.lineId === selectedLineId) ?? null
  const selectedGame = filteredGames.find(game => game.gameId === selectedLine?.gameId) ?? null
  // A position or week change can empty the chosen market, so fall back rather than show nothing.
  useEffect(() => { setMarket(null) }, [activeSeason, activeWeek, position])
  useEffect(() => { setSelectedLineId(null) }, [activeSeason, activeWeek, position, selectedMarket, gameFilter, showAll])
  if (currentWeek.isError && (season === null || week === null)) return <ErrorState error={currentWeek.error} onRetry={() => currentWeek.refetch()} />
  if (activeSeason === null || activeWeek === null) return <LoadingState message="Loading NFL prop board..." />
  return <div className="page-shell nfl-slate nfl-prop-board"><div className="page-container is-wide">
    <NflPropBoardHead season={activeSeason} week={activeWeek} games={availableGames.length} categories={categories}
      lineOnlyCount={otherCategories.reduce((total, item) => total + item.count, 0)}
      onSeason={value => { setSeason(value); setWeek(activeWeek); setGameFilter('all') }}
      onWeek={value => { setSeason(activeSeason); setWeek(value); setGameFilter('all') }} />
    <NflMarketPills categories={pills} selected={selectedMarket} onSelect={setMarket} />
    <NflPropBoardFilters position={position} gameFilter={gameFilter} games={availableGames} showAll={showAll} showLineToggle={!otherCategory}
      onPosition={setPosition} onGame={setGameFilter} onShowAll={setShowAll} />
    {slate.isLoading && <LoadingState message="Loading prop comparisons..." />}
    {slate.isError && <ErrorState error={slate.error} onRetry={() => void slate.refetch()} />}
    {lineOnly.isLoading && <LoadingState message="Loading other markets..." />}
    {lineOnly.isError && <ErrorState error={lineOnly.error} onRetry={() => void lineOnly.refetch()} />}
    {otherCategory && <section className="nfl-prop-board__other" aria-label={`${marketLabel(otherCategory.market)} recent results`}>
      <p className="nfl-prop-table-empty">Recent results only. No model projection, edge, or ranking. Standard and alternate lines are shown together.</p>
      {otherCategory.games.map(({ game, group }) => <section key={game.gameId} className="prop-table-panel" aria-label={`${game.awayTeam} at ${game.homeTeam}`}>
        <h3 className="nfl-game-label"><Link to={`/nfl/game/${game.gameId}`}>{game.awayTeam} @ {game.homeTeam}</Link> · {formatKickoffTime(game.startUtc)}</h3>
        <NflLineOnlyTable group={group} />
      </section>)}
    </section>}
    {category && <>
      <section className="prop-table-panel" aria-label="Prop lines">
        {category.rateable.length === 0 && <p className="nfl-prop-table-empty">{isTargetsReference(category.market) ? 'No standard full-game Rec Targets references available.' : `No rateable ${marketLabel(category.market).toLowerCase()} lines this week.`}</p>}
        <NflPropTable category={category} now={Date.now()} selectedLineId={selectedLine?.lineId ?? null} onOpen={row => { drawerFocus.rememberTrigger(row.lineId); setSelectedLineId(row.lineId) }}
          rateable={category.rateable.map((row, index) => ({ row, rank: isTargetsReference(row.market) ? null : index + 1 }))}
          other={showAll ? category.other.map(row => ({ row, rank: null })) : []} />
      </section>
      <Drawer open={selectedLine !== null} onClose={() => setSelectedLineId(null)} afterOpenChange={drawerFocus.afterOpenChange} width={isMobile ? '100%' : 460} title={null} className="nfl-slate nfl-game nfl-game-drawer" destroyOnHidden>
        {selectedLine && <NflEvidencePanel row={selectedLine} game={selectedGame} alternates={alternates.get(selectedLine.lineId) ?? []} />}
      </Drawer>
    </>}
    {!pills.length && slate.isSuccess && lineOnly.isSuccess && <div className="nfl-empty">No upcoming prop lines for these filters. Choose another position, game, or week.</div>}
  </div></div>
}
