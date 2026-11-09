import { Select } from 'antd'
import { useMemo } from 'react'
import { Link, Navigate, useNavigate, useSearchParams } from 'react-router-dom'
import { NflSlateDigest } from '~/components/nfl/NflSlateDigest'
import { NflSlateTable } from '~/components/nfl/NflSlateTable'
import ErrorState from '~/components/shared/ErrorState'
import LoadingState from '~/components/shared/LoadingState'
import PageHead from '~/components/shared/PageHead'
import SlateLegend from '~/components/shared/SlateLegend'
import { useRegisterSlateCommand, useSlateCommand } from '~/components/shared/SlateCommandProvider'
import { useNflCurrentWeek, useNflGameNotes, useNflSlate } from '~/hooks/useNfl'
import { usePhoneLayout } from '~/hooks/usePhoneLayout'
import type { NflGameNotes, NflSlateGame } from '~/types/nfl'
import { parseGameId } from '~/utils/nflGame'
import { buildNflPropBoard } from '~/utils/nflPropBoard'
import { kickoffWindows, nflSlateRow, nflSlateSummary, searchedKickoffWindow, slateDigest } from '~/utils/nflSlate'
import { type NflWeek, nflWeekKey, nflWeekNeighbors, nflWeekPath, nflWeekPickerOptions, parseNflWeekKey, readNflWeekLink } from '~/utils/nflWeekPeriod'
import { matchingSlateCommandRows, nflSlateCommandRows, normalizeSlateCommand } from '~/utils/slateCommand'
import { SLATE_LEGENDS } from '~/utils/slateLegend'
import { gameSlateLine, startTimes } from '~/utils/slatePeriod'
import './nfl-slate.css'

const WEEK_OPTIONS = nflWeekPickerOptions()

function periodLine(week: number, games: NflSlateGame[], notes: NflGameNotes[] | undefined): string {
  return gameSlateLine(`Week ${week}`, nflSlateSummary(games, notes), startTimes(games.map(game => game.startUtc)), Date.now())
}

function WeekPicker({ active }: { active: NflWeek }) {
  const navigate = useNavigate()
  return <Select
    aria-label="Week"
    value={nflWeekKey(active)}
    options={WEEK_OPTIONS}
    labelRender={() => `${active.season} · Week ${active.week}`}
    onChange={(key: string) => {
      const picked = parseNflWeekKey(key)
      if (picked) navigate(nflWeekPath(picked))
    }}
  />
}

function nextWeekLabel(active: NflWeek, next: NflWeek): string {
  return next.season === active.season ? `Week ${next.week}` : `${next.season} Week ${next.week}`
}

export default function NflIntelligencePage() {
  const [searchParams] = useSearchParams()
  const legacyGameId = parseGameId(searchParams.get('gameId') ?? undefined)
  // A missing or invalid value follows the current week.
  const { season, week } = readNflWeekLink(searchParams)
  const currentWeek = useNflCurrentWeek()
  const activeSeason = season ?? currentWeek.data?.season ?? null
  const activeWeek = week ?? currentWeek.data?.week ?? null
  const slate = useNflSlate(activeSeason, activeWeek)
  const gameNotes = useNflGameNotes(activeSeason, activeWeek)
  const games = useMemo(() => slate.data?.games ?? [], [slate.data])
  const notes = gameNotes.data?.games
  const rows = useMemo(() => {
    const now = new Date()
    const notesById = new Map((notes ?? []).map(item => [item.gameId, item]))
    return new Map(games.map(game => [game.gameId, nflSlateRow(game, notesById.get(game.gameId), now)]))
  }, [games, notes])
  // As of now, so only games not yet kicked off can reach the digest.
  const digest = useMemo(() => slateDigest(buildNflPropBoard(games, 'all', new Date())), [games])
  const windows = useMemo(() => kickoffWindows(games), [games])
  const { query } = useSlateCommand()
  const phone = usePhoneLayout()
  const orderedGames = useMemo(() => windows.flatMap(window => window.games), [windows])
  const commandRows = useMemo(() => nflSlateCommandRows(orderedGames), [orderedGames])
  const commandScope = useMemo(() => activeSeason === null || activeWeek === null || slate.isLoading || slate.isError
    ? null
    : { periodKey: `${activeSeason}-${activeWeek}`, rows: commandRows },
  [activeSeason, activeWeek, commandRows, slate.isError, slate.isLoading])
  useRegisterSlateCommand(commandScope)
  const commandActive = normalizeSlateCommand(query).length > 0
  const filteredWindows = useMemo(() => {
    if (!commandActive) return windows
    const gameIds = new Set(matchingSlateCommandRows(commandRows, query).map(row => Number(row.path.split('/').at(-1))))
    return windows.flatMap(window => {
      const matchingGames = window.games.filter(game => gameIds.has(game.gameId))
      return matchingGames.length > 0 ? [searchedKickoffWindow(window, matchingGames)] : []
    })
  }, [commandActive, commandRows, query, windows])

  // The old slate opened one game from ?gameId=; that game now has its own page.
  if (legacyGameId !== null) return <Navigate to={`/nfl/game/${legacyGameId}`} replace />
  if (currentWeek.isError && (season === null || week === null)) return <ErrorState error={currentWeek.error} onRetry={() => currentWeek.refetch()} />
  if (activeSeason === null || activeWeek === null) return <LoadingState message="Loading NFL slate..." />
  const active = { season: activeSeason, week: activeWeek }
  const { previous, next } = nflWeekNeighbors(active)
  return <div className="page-shell nfl-slate is-game-slate"><div className="page-container is-wide">
    <PageHead
      title="NFL slate"
      meta={periodLine(activeWeek, slate.isSuccess ? games : [], notes)}
      period={{
        label: 'NFL week',
        previous: previous && nflWeekPath(previous),
        next: next && nflWeekPath(next),
        picker: <WeekPicker active={active} />,
      }}
    />
    {/* A stored-snapshot miss (503 in production) keeps the page head, so Previous and Next still work. */}
    {slate.isLoading ? <LoadingState message="Loading NFL slate..." />
      : slate.isError ? <ErrorState error={slate.error} onRetry={() => slate.refetch()} />
      : games.length === 0 ? <div className="nfl-empty">
        No NFL games loaded for week {activeWeek}.{' '}
        {next && <Link className="nfl-empty__next" to={nflWeekPath(next)}>{nextWeekLabel(active, next)} →</Link>}
      </div> : <>
        <NflSlateDigest items={digest} />
        {!phone && <SlateLegend {...SLATE_LEGENDS.nfl} />}
        {commandActive && filteredWindows.length === 0 && <section className="nfl-slate-window" aria-label="Games">
          <div className="nfl-empty">No games found for this slate search.</div>
        </section>}
        {filteredWindows.map(window => <section key={window.key} className="nfl-slate-window" aria-label={window.title}>
          <h2 className="nfl-slate-window__title">{window.title} <small>{window.subtitle}</small></h2>
          <NflSlateTable label={`${window.title} games`} rows={window.games.flatMap(game => rows.get(game.gameId) ?? [])} />
        </section>)}
        {/* Phones put the source legend after the games, so the first rows reach the first screen. */}
        {phone && <SlateLegend {...SLATE_LEGENDS.nfl} />}
      </>}
  </div></div>
}
