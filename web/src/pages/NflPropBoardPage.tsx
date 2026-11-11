import { useMemo } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { NflLineOnlyTable } from '~/components/nfl/NflLineOnlyProps'
import { NflMarketPills, NflPropBoardFilters, NflPropBoardHead } from '~/components/nfl/NflPropBoardControls'
import { NflPropTable } from '~/components/nfl/NflPropTable'
import { NflSlateDigest } from '~/components/nfl/NflSlateDigest'
import ErrorState from '~/components/shared/ErrorState'
import LoadingState from '~/components/shared/LoadingState'
import { useNflCurrentWeek, useNflSlate, useNflWeekLineOnlyProps } from '~/hooks/useNfl'
import { useRestoreOpenedRow } from '~/hooks/useRestoreOpenedRow'
import { formatKickoffTime, marketLabel } from '~/utils/nflLabels'
import { buildNflPropBoard, filterNflBoardCategories, filterNflPropBoardGames } from '~/utils/nflPropBoard'
import { slateDigest } from '~/utils/nflSlate'
import { isTargetsReference } from '~/utils/nflTargets'
import { boardViewSearch, parseBoardView, type NflBoardView } from '~/utils/nflViewParams'
import { availableNflPropGames, filterNflWeekLineOnly, nflWeekLineOnlyCategories } from '~/utils/nflWeekLineOnly'
import { ALL, activeTeamFilter, gameTeams, isFiltering, teamAfterGame, visibleMarket } from '~/utils/propFilters'
import './nfl-slate.css'
import './nfl-prop-board.css'

export default function NflPropBoardPage() {
  // The view lives in the URL so Back from a player page returns to it. Null season and week follow the current week; a pick pins them.
  const [params, setParams] = useSearchParams()
  const view = useMemo(() => parseBoardView(params), [params])
  const { season, week, position, market, game: gameFilter, showAll, q } = view
  const update = (patch: Partial<NflBoardView>) => setParams(boardViewSearch({ ...view, ...patch }), { replace: true })
  const currentWeek = useNflCurrentWeek()
  const activeSeason = season ?? currentWeek.data?.season ?? null
  const activeWeek = week ?? currentWeek.data?.week ?? null
  const slate = useNflSlate(activeSeason, activeWeek)
  const lineOnly = useNflWeekLineOnlyProps(activeSeason, activeWeek)
  useRestoreOpenedRow(slate.isSuccess)
  const availableGames = useMemo(() => availableNflPropGames(slate.data?.games ?? [], lineOnly.data?.games ?? []), [slate.data, lineOnly.data])
  const selectedGameId = gameFilter === 'all' ? null : Number(gameFilter)
  const filteredGames = useMemo(() => filterNflPropBoardGames(slate.data?.games ?? [], selectedGameId), [slate.data, selectedGameId])
  const categories = useMemo(() => buildNflPropBoard(filteredGames, position), [filteredGames, position])
  const otherCategories = useMemo(() => nflWeekLineOnlyCategories(lineOnly.data?.games ?? [], position, selectedGameId), [lineOnly.data, position, selectedGameId])
  // The slate's own digest: the whole week as of now, ignoring the board's filters.
  const digest = useMemo(() => slateDigest(buildNflPropBoard(slate.data?.games ?? [], 'all', new Date())), [slate.data])
  const teams = useMemo(() => gameTeams(availableGames), [availableGames])
  const team = activeTeamFilter(view.team, teams)
  const filtered = useMemo(() => filterNflBoardCategories(categories, q, team), [categories, q, team])
  const filteredOther = useMemo(() => filterNflWeekLineOnly(otherCategories, q, team), [otherCategories, q, team])
  const filtering = isFiltering({ q, team, game: ALL })
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
  if (currentWeek.isError && (season === null || week === null)) return <ErrorState error={currentWeek.error} onRetry={() => currentWeek.refetch()} />
  if (activeSeason === null || activeWeek === null) return <LoadingState message="Loading NFL prop board..." />
  return <div className="page-shell nfl-slate nfl-prop-board"><div className="page-container is-wide">
    <NflPropBoardHead season={activeSeason} week={activeWeek} games={availableGames.length} categories={categories}
      lineOnlyCount={otherCategories.reduce((total, item) => total + item.count, 0)}
      onSeason={value => update({ season: value, week: activeWeek, game: 'all', market: null, q: '', team: ALL })}
      onWeek={value => update({ season: activeSeason, week: value, game: 'all', market: null, q: '', team: ALL })} />
    <NflSlateDigest items={digest} />
    <NflMarketPills categories={pills} selected={selectedMarket} onSelect={value => update({ market: value })} />
    <NflPropBoardFilters position={position} gameFilter={gameFilter} games={availableGames} showAll={showAll} showLineToggle={!otherCategory} query={q} team={team} teams={teams}
      onPosition={value => update({ position: value, market: null })} onGame={value => update({ game: value, team: teamAfterGame(team, value, availableGames) })} onShowAll={value => update({ showAll: value })}
      onQuery={value => update({ q: value })} onTeam={value => update({ team: value })} />
    {slate.isLoading && <LoadingState message="Loading prop comparisons..." />}
    {slate.isError && <ErrorState error={slate.error} onRetry={() => void slate.refetch()} />}
    {lineOnly.isLoading && <LoadingState message="Loading other markets..." />}
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
          other={showAll ? selected.other.map(row => ({ row, rank: null })) : []} />
      </section>
    </>}
    {!pills.length && slate.isSuccess && lineOnly.isSuccess && <div className="nfl-empty">No upcoming prop lines for these filters. Choose another position, game, or week.</div>}
  </div></div>
}
