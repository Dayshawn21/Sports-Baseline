import { Select } from 'antd'
import { useCallback, useMemo } from 'react'
import { Link, Navigate, useNavigate, useSearchParams } from 'react-router-dom'
import { NFL_GAPS_ORDER, nflGapLink } from '~/components/nfl/NflSlateDigest'
import { NflSlateTable } from '~/components/nfl/NflSlateTable'
import ErrorState from '~/components/shared/ErrorState'
import TableSkeleton from '~/components/shared/TableSkeleton'
import PageHead from '~/components/shared/PageHead'
import SlateFinalsWindow from '~/components/shared/SlateFinalsWindow'
import SlateLegend from '~/components/shared/SlateLegend'
import { SlateNoPicks } from '~/components/shared/SlateNoPicks'
import { useRegisterSlateCommand, useSlateCommand } from '~/components/shared/SlateCommandProvider'
import { useNflCurrentWeek, useNflGameNotes, useNflSlate } from '~/hooks/useNfl'
import { usePhoneLayout } from '~/hooks/usePhoneLayout'
import type { NflGameNotes, NflSlateGame } from '~/types/nfl'
import { parseGameId } from '~/utils/nflGame'
import { buildNflPropBoard } from '~/utils/nflPropBoard'
import { kickoffWindows, type NflSlateRowModel, nflSlateRow, nflSlateSummary, searchedKickoffWindow, slateDigest } from '~/utils/nflSlate'
import { type NflWeek, nflWeekKey, nflWeekNeighbors, nflWeekPath, nflWeekPickerOptions, parseNflWeekKey, readNflWeekLink } from '~/utils/nflWeekPeriod'
import { commandGameContext, matchingSlateCommandRows, nflSlateCommandRows, normalizeSlateCommand } from '~/utils/slateCommand'
import { slateRemainingLine } from '~/utils/slateHeadline'
import { SLATE_LEGENDS } from '~/utils/slateLegend'
import { finalsStartOpen, orderWindowsByPhase, slatePhase, splitFinals } from '~/utils/slateOrder'
import { gameSlateLine, slatePeriodLine, staleOddsSince, startTimes, tableCountPart, windowOddsNote } from '~/utils/slatePeriod'
import './nfl-slate.css'

const WEEK_OPTIONS = nflWeekPickerOptions()

function periodLine(week: number, games: NflSlateGame[], notes: NflGameNotes[] | undefined): string {
  return gameSlateLine(`Week ${week}`, nflSlateSummary(games, notes), startTimes(games.map(game => game.startUtc)), Date.now())
}

const STATE_LABEL: Partial<Record<NflSlateRowModel['state'], string>> = { final: 'Final', pending: 'Result pending', live: 'Live' }

/** A search result's second line: kickoff, state, or the final score. */
function commandContext(row: NflSlateRowModel | undefined): string | undefined {
  if (!row) return undefined
  return commandGameContext(STATE_LABEL[row.state] ?? row.kickoff, row.state === 'final' ? row : undefined)
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
  const { rows, staleSince, nowMs } = useMemo(() => {
    const now = new Date()
    const notesById = new Map((notes ?? []).map(item => [item.gameId, item]))
    // The period line's own check: while the odds are stale, a row shows its age only when it differs from the head's.
    const stale = staleOddsSince(nflSlateSummary(games, notes).oddsUpdatedMs, startTimes(games.map(game => game.startUtc)), now.getTime())
    return { rows: new Map(games.map(game => [game.gameId, nflSlateRow(game, notesById.get(game.gameId), now, stale)])), staleSince: stale, nowMs: now.getTime() }
  }, [games, notes])
  const staleOdds = staleSince !== null
  // As of now, so only games not yet kicked off can reach the digest.
  const digest = useMemo(() => slateDigest(buildNflPropBoard(games, 'all', new Date())), [games])
  const remaining = useMemo(() => slateRemainingLine(games.map(game => ({ state: rows.get(game.gameId)?.state ?? 'upcoming', startUtc: game.startUtc })), Date.now()), [games, rows])
  const phaseOf = useCallback((game: NflSlateGame) => slatePhase(rows.get(game.gameId)?.state ?? 'upcoming'), [rows])
  // Display order only: windows with a live game lead, and every final goes to one closed window at the end.
  const { windows, finals } = useMemo(() => {
    const split = splitFinals(games, phaseOf)
    return {
      windows: orderWindowsByPhase(kickoffWindows(split.open), phaseOf),
      finals: kickoffWindows(split.finals).flatMap(window => window.games),
    }
  }, [games, phaseOf])
  const { query } = useSlateCommand()
  const phone = usePhoneLayout()
  const orderedGames = useMemo(() => [...windows.flatMap(window => window.games), ...finals], [windows, finals])
  const commandRows = useMemo(
    () => nflSlateCommandRows(orderedGames.map(game => ({ ...game, commandContext: commandContext(rows.get(game.gameId)) }))),
    [orderedGames, rows],
  )
  const commandScope = useMemo(() => activeSeason === null || activeWeek === null || slate.isLoading || slate.isError
    ? null
    : { periodKey: `${activeSeason}-${activeWeek}`, rows: commandRows },
  [activeSeason, activeWeek, commandRows, slate.isError, slate.isLoading])
  useRegisterSlateCommand(commandScope)
  const commandActive = normalizeSlateCommand(query).length > 0
  const { filteredWindows, filteredFinals } = useMemo(() => {
    if (!commandActive) return { filteredWindows: windows, filteredFinals: finals }
    const gameIds = new Set(matchingSlateCommandRows(commandRows, query).map(row => Number(row.path.split('/').at(-1))))
    return {
      filteredWindows: windows.flatMap(window => {
        const matchingGames = window.games.filter(game => gameIds.has(game.gameId))
        return matchingGames.length > 0 ? [searchedKickoffWindow(window, matchingGames)] : []
      }),
      filteredFinals: finals.filter(game => gameIds.has(game.gameId)),
    }
  }, [commandActive, commandRows, finals, query, windows])
  const tableRows = (list: NflSlateGame[]) => list.flatMap(game => rows.get(game.gameId) ?? [])
  // One table now holds every window, so the stale-odds age names itself once, on the first window with an unplayed game.
  const firstOddsNoteIndex = filteredWindows.findIndex(window => windowOddsNote(staleSince, window.games.map(phaseOf), nowMs) !== null)

  // The old slate opened one game from ?gameId=; that game now has its own page.
  if (legacyGameId !== null) return <Navigate to={`/nfl/game/${legacyGameId}`} replace />
  if (currentWeek.isError && (season === null || week === null)) return <ErrorState error={currentWeek.error} onRetry={() => currentWeek.refetch()} />
  if (activeSeason === null || activeWeek === null) return <div className="page-shell nfl-slate is-game-slate"><div className="page-container is-wide">
    <PageHead title="NFL slate" />
    <TableSkeleton label="Loading NFL slate..." columns={8} />
  </div></div>
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
    {slate.isLoading ? <TableSkeleton label="Loading NFL slate..." columns={8} />
      : slate.isError ? <ErrorState error={slate.error} onRetry={() => slate.refetch()} />
      : games.length === 0 ? <div className="nfl-empty">
        No NFL games loaded for week {activeWeek}.{' '}
        {next && <Link className="nfl-empty__next" to={nflWeekPath(next)}>{nextWeekLabel(active, next)} →</Link>}
      </div> : <>
        <SlateNoPicks
          sport="nfl" remaining={remaining} gaps={digest.map(item => nflGapLink(item))}
          gapsLabel="Top gaps" gapsOrder={NFL_GAPS_ORDER}
        />
        {!phone && <SlateLegend {...SLATE_LEGENDS.nfl} />}
        {commandActive && filteredWindows.length === 0 && filteredFinals.length === 0 && <section className="nfl-slate-window" aria-label="Games">
          <div className="nfl-empty">No games found for this slate search.</div>
        </section>}
        {filteredWindows.length > 0 && <section className="nfl-slate-window" aria-label="Games">
          <NflSlateTable label="Games by kickoff" staleOdds={staleOdds} groups={filteredWindows.map((window, index) => ({
            key: window.key,
            title: window.title,
            note: slatePeriodLine([window.subtitle, index === firstOddsNoteIndex ? windowOddsNote(staleSince, window.games.map(phaseOf), nowMs) : null]),
            rows: tableRows(window.games),
          }))} />
        </section>}
        {filteredFinals.length > 0 && <SlateFinalsWindow
          key={`${activeSeason}-${activeWeek}-${commandActive}`}
          subtitle={tableCountPart(filteredFinals.length, finals.length, commandActive, 'game')}
          startOpen={finalsStartOpen(windows.length, commandActive)}
        >
          <NflSlateTable label="Final games" groups={[{ key: 'final', title: null, rows: tableRows(filteredFinals) }]} />
        </SlateFinalsWindow>}
        {/* Phones put the source legend after the games, so the first rows reach the first screen. */}
        {phone && <SlateLegend {...SLATE_LEGENDS.nfl} />}
      </>}
  </div></div>
}
