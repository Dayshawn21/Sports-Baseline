import { useMemo } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { NflLineOnlyTable } from '~/components/nfl/NflLineOnlyProps'
import { NflMarketPills, NflPropBoardFilters, NflPropBoardHead } from '~/components/nfl/NflPropBoardControls'
import { NflPropTable } from '~/components/nfl/NflPropTable'
import { NflSlateDigest } from '~/components/nfl/NflSlateDigest'
import BoardRecordStrip from '~/components/shared/BoardRecordStrip'
import ErrorState from '~/components/shared/ErrorState'
import TableSkeleton from '~/components/shared/TableSkeleton'
import { useNflCurrentWeek, useNflSlate, useNflWeekLineOnlyProps } from '~/hooks/useNfl'
import { useNflModelRanking } from '~/hooks/useNflModelTrackRecord'
import { useRestoreOpenedRow } from '~/hooks/useRestoreOpenedRow'
import { rankingBoardRecord, recordStatus } from '~/utils/boardRecord'
import { formatKickoffTime, marketLabel } from '~/utils/nflLabels'
import { buildNflPropBoard, filterNflBoardCategories, filterNflPropBoardGames } from '~/utils/nflPropBoard'
import { slateDigest } from '~/utils/nflSlate'
import { isTargetsReference } from '~/utils/nflTargets'
import { boardViewSearch, parseBoardView, type NflBoardView } from '~/utils/nflViewParams'
import { availableNflPropGames, filterNflWeekLineOnly, nflBoardPlayerOptions, nflWeekLineOnlyCategories } from '~/utils/nflWeekLineOnly'
import { ALL, activeGameFilters, activeTeamFilter, gameTeams, isFiltering, teamAfterGames, visibleMarket } from '~/utils/propFilters'
import './nfl-slate.css'
import './nfl-prop-board.css'

export default function NflPropBoardPage() {
  // The view lives in the URL so Back from a player page returns to it. Null season and week follow the current week; a pick pins them.
  const [params, setParams] = useSearchParams()
  const view = useMemo(() => parseBoardView(params), [params])
  const { season, week, position, market, showAll, players } = view
  const update = (patch: Partial<NflBoardView>) => setParams(boardViewSearch({ ...view, ...patch }), { replace: true })
  const currentWeek = useNflCurrentWeek()
  const activeSeason = season ?? currentWeek.data?.season ?? null
  const activeWeek = week ?? currentWeek.data?.week ?? null
  const slate = useNflSlate(activeSeason, activeWeek)
  const lineOnly = useNflWeekLineOnlyProps(activeSeason, activeWeek)
  useRestoreOpenedRow(slate.isSuccess)
  const availableGames = useMemo(() => availableNflPropGames(slate.data?.games ?? [], lineOnly.data?.games ?? []), [slate.data, lineOnly.data])
  const gameFilter = useMemo(() => activeGameFilters(view.games, availableGames), [view.games, availableGames])
  const selectedGameIds = useMemo(() => gameFilter.map(Number), [gameFilter])
  const filteredGames = useMemo(() => filterNflPropBoardGames(slate.data?.games ?? [], selectedGameIds), [slate.data, selectedGameIds])
  const categories = useMemo(() => buildNflPropBoard(filteredGames, position), [filteredGames, position])
  const otherCategories = useMemo(() => nflWeekLineOnlyCategories(lineOnly.data?.games ?? [], position, selectedGameIds), [lineOnly.data, position, selectedGameIds])
  // The slate's own digest: the whole week as of now, ignoring the board's filters.
  const digest = useMemo(() => slateDigest(buildNflPropBoard(slate.data?.games ?? [], 'all', new Date())), [slate.data])
  const teams = useMemo(() => gameTeams(availableGames), [availableGames])
  const team = activeTeamFilter(view.team, teams)
  const filtered = useMemo(() => filterNflBoardCategories(categories, players, team), [categories, players, team])
  const filteredOther = useMemo(() => filterNflWeekLineOnly(otherCategories, players, team), [otherCategories, players, team])
  const playerNames = useMemo(() => nflBoardPlayerOptions(categories, otherCategories, team, players, showAll), [categories, otherCategories, team, players, showAll])
  const filtering = isFiltering({ players, team, games: [] })
  const pills = [...filtered.map(item => ({ market: item.category.market, count: item.rateable.length })), ...filteredOther.map(item => ({ market: item.market, count: item.count }))]
  const choosableMarket = pills.some(item => item.market === market) ? market
    : filtered.find(item => item.rateable.length > 0)?.category.market ?? pills[0]?.market ?? null
  const selectedMarket = visibleMarket(choosableMarket, [
    ...filtered.map(item => ({ market: item.category.market, count: item.rateable.length + (showAll ? item.other.length : 0) })),
    ...filteredOther.map(item => ({ market: item.market, count: item.count })),
  ], filtering)
  const selected = filtered.find(item => item.category.market === selectedMarket) ?? null
  const category = selected?.category ?? null
  const otherCategory = filteredOther.find(item => item.market === selectedMarket)
  const noMatches = filtering && !filtered.some(item => item.rateable.length > 0 || (showAll && item.other.length > 0)) && filteredOther.length === 0
  // The board serves v4, so the strip reads v4's season record, not the week's.
  const ranking = useNflModelRanking(activeSeason)
  const record = rankingBoardRecord('nfl', ranking.data, recordStatus(ranking))
  if (currentWeek.isError && (season === null || week === null)) return <ErrorState error={currentWeek.error} onRetry={() => currentWeek.refetch()} />
  if (activeSeason === null || activeWeek === null) return <div className="page-shell nfl-slate nfl-prop-board"><div className="page-container is-wide">
    <TableSkeleton label="Loading NFL prop board..." columns={6} rows={5} rowHeight={157} stackedRowHeight={221} variant="board" />
  </div></div>
  return <div className="page-shell nfl-slate nfl-prop-board"><div className="page-container is-wide">
    <NflPropBoardHead season={activeSeason} week={activeWeek} games={availableGames.length}
      onSeason={value => update({ season: value, week: activeWeek, games: [], market: null, players: [], team: ALL })}
      onWeek={value => update({ season: activeSeason, week: value, games: [], market: null, players: [], team: ALL })} />
    <BoardRecordStrip record={record} />
    <NflSlateDigest items={digest} />
    <NflMarketPills categories={pills} selected={selectedMarket} onSelect={value => update({ market: value })} />
    <NflPropBoardFilters position={position} gameFilter={gameFilter} games={availableGames} showAll={showAll} showLineToggle={!otherCategory} players={players} playerNames={playerNames} team={team} teams={teams}
      onPosition={value => update({ position: value, market: null })} onGames={value => update({ games: value, team: teamAfterGames(team, value, availableGames) })} onShowAll={value => update({ showAll: value })}
      onPlayers={value => update({ players: value })} onTeam={value => update({ team: value })} />
    {slate.isLoading && <TableSkeleton label="Loading prop comparisons..." columns={6} rows={5} rowHeight={157} stackedRowHeight={221} variant="board" />}
    {slate.isError && <ErrorState error={slate.error} onRetry={() => void slate.refetch()} />}
    {lineOnly.isLoading && <TableSkeleton label="Loading other markets..." columns={6} rows={3} rowHeight={157} stackedRowHeight={221} variant="board" />}
    {lineOnly.isError && <ErrorState error={lineOnly.error} onRetry={() => void lineOnly.refetch()} />}
    {noMatches && <div className="nfl-empty">No lines match these filters. Clear the search or choose another team or game.</div>}
    {!noMatches && otherCategory && <section className="nfl-prop-board__other" aria-label={`${marketLabel(otherCategory.market)} recent results`}>
      <p className="nfl-prop-table-empty">Recent results only. No model projection, edge, or ranking. Standard and alternate lines are shown together.</p>
      {otherCategory.games.map(({ game, group }) => <section key={game.gameId} className="prop-table-panel" aria-label={`${game.awayTeam} at ${game.homeTeam}`}>
        <h3 className="nfl-game-label"><Link to={`/nfl/game/${game.gameId}`}>{game.awayTeam} @ {game.homeTeam}</Link> · {formatKickoffTime(game.startUtc)}</h3>
        <NflLineOnlyTable group={group} week={{ season: activeSeason, week: activeWeek }} />
      </section>)}
    </section>}
    {!noMatches && selected && category && <>
      <section className="prop-table-panel" aria-label="Prop lines">
        {selected.rateable.length === 0 && <p className="nfl-prop-table-empty">{isTargetsReference(category.market) ? 'No standard full-game Rec Targets references available.' : `No rateable ${marketLabel(category.market).toLowerCase()} lines this week.`}</p>}
        <NflPropTable category={category} now={Date.now()} week={{ season: activeSeason, week: activeWeek }}
          rateable={selected.rateable}
          other={showAll ? selected.other : []} />
      </section>
    </>}
    {!pills.length && slate.isSuccess && lineOnly.isSuccess && <div className="nfl-empty">No upcoming prop lines for these filters. Choose another position, game, or week.</div>}
  </div></div>
}
