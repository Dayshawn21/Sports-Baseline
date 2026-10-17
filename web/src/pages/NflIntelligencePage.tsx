import { Select } from 'antd'
import { useMemo, useRef, useState } from 'react'
import { Navigate, useSearchParams } from 'react-router-dom'
import { NflSlateDigest } from '~/components/nfl/NflSlateDigest'
import { NflSlateTable } from '~/components/nfl/NflSlateTable'
import ErrorState from '~/components/shared/ErrorState'
import LoadingState from '~/components/shared/LoadingState'
import PageHead from '~/components/shared/PageHead'
import StatChip from '~/components/shared/StatChip'
import { useNflCurrentWeek, useNflGameNotes, useNflSlate } from '~/hooks/useNfl'
import type { NflGameNotes, NflSlateGame } from '~/types/nfl'
import { parseGameId } from '~/utils/nflGame'
import { NFL_SEASON_OPTIONS, NFL_WEEK_OPTIONS } from '~/utils/nflLabels'
import { buildNflPropBoard } from '~/utils/nflPropBoard'
import { kickoffWindows, nflSlateRow, nflSlateSummary, slateDigest } from '~/utils/nflSlate'
import './nfl-slate.css'

const MISSING = '--'

/** Seeds the week from a link; an unparseable value falls back to the current week. */
function readWeekLink(params: URLSearchParams) {
  const number = (key: string) => {
    const value = Number(params.get(key))
    return params.has(key) && Number.isInteger(value) ? value : null
  }
  return { season: number('season'), week: number('week') }
}

function Summary({ games, notes }: { games: NflSlateGame[], notes: NflGameNotes[] | undefined }) {
  const summary = nflSlateSummary(games, notes)
  return <section className="page-head__stats nfl-slate__stats" aria-label="Week summary">
    <StatChip value={summary.games} label="Games" />
    <StatChip value={summary.propLines} label="Prop lines" />
    <StatChip value={`${summary.finals} / ${summary.games}`} label="Final" />
    <StatChip value={summary.outOrDoubtful ?? MISSING} label="Out or doubtful" />
    <StatChip value={summary.oddsUpdated ?? MISSING} label="Odds updated" />
  </section>
}

function Legend() {
  return <p className="nfl-slate__legend">
    <span><b>Market</b> is DraftKings when stored, else the latest book.</span>
    <span><b>Model</b> is nfl-elo-v1, shown for context. It is not a pick: the closing line beat it on the 2022-25 holdout.</span>
    <span><b>Gaps</b> are reference, not picks: they stay gray until the ranking check (27j) adopts a slice.</span>
  </p>
}

export default function NflIntelligencePage() {
  const [searchParams] = useSearchParams()
  const legacyGameId = parseGameId(searchParams.get('gameId') ?? undefined)
  const seeded = useRef(readWeekLink(searchParams)).current
  // Null follows the current week; a link or a user's pick pins it.
  const [season, setSeason] = useState<number | null>(seeded.season)
  const [week, setWeek] = useState<number | null>(seeded.week)
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

  // The old slate opened one game from ?gameId=; that game now has its own page.
  if (legacyGameId !== null) return <Navigate to={`/nfl/game/${legacyGameId}`} replace />
  if (currentWeek.isError && (season === null || week === null)) return <ErrorState error={currentWeek.error} onRetry={() => currentWeek.refetch()} />
  if (activeSeason === null || activeWeek === null || slate.isLoading) return <LoadingState message="Loading NFL slate..." />
  if (slate.isError) return <ErrorState error={slate.error} onRetry={() => slate.refetch()} />
  return <div className="page-shell nfl-slate"><div className="page-container is-wide">
    <PageHead
      title="NFL slate"
      meta={`${activeSeason} · Week ${activeWeek}`}
      actions={<>
        <Select aria-label="Season" value={activeSeason} onChange={value => { setSeason(value); setWeek(activeWeek) }} options={NFL_SEASON_OPTIONS} />
        <Select aria-label="Week" value={activeWeek} onChange={value => { setSeason(activeSeason); setWeek(value) }} options={NFL_WEEK_OPTIONS} />
      </>}
      stats={games.length > 0 && <Summary games={games} notes={notes} />}
    />
    {games.length === 0 ? <div className="nfl-empty">No games loaded for this season and week.</div> : <>
      <NflSlateDigest items={digest} />
      <Legend />
      {windows.map(window => <section key={window.key} className="nfl-slate-window" aria-label={window.title}>
        <h2 className="nfl-slate-window__title">{window.title} <small>{window.subtitle}</small></h2>
        <NflSlateTable label={`${window.title} games`} rows={window.games.flatMap(game => rows.get(game.gameId) ?? [])} />
      </section>)}
    </>}
  </div></div>
}
