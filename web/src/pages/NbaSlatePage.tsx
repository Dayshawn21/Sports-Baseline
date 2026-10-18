import { useMemo } from 'react'
import { useSearchParams } from 'react-router-dom'
import { NbaSlateDigest } from '~/components/nba/NbaSlateDigest'
import { NbaSlateTable } from '~/components/nba/NbaSlateTable'
import ErrorState from '~/components/shared/ErrorState'
import LoadingState from '~/components/shared/LoadingState'
import PageHead from '~/components/shared/PageHead'
import StatChip from '~/components/shared/StatChip'
import { useRegisterSlateCommand, useSlateCommand } from '~/components/shared/SlateCommandProvider'
import { useNbaSlate, useNbaSlateGaps } from '~/hooks/useNba'
import type { NbaSlateGame } from '~/types/nba'
import { nbaSlateDigest, nbaSlateRow, nbaSlateSummary, parseSlateDate, slateDateLabel } from '~/utils/nbaSlate'
import { matchingSlateCommandRows, nbaSlateCommandRows, normalizeSlateCommand } from '~/utils/slateCommand'
import './nfl-slate.css'

const MISSING = '--'

function Summary({ games }: { games: NbaSlateGame[] }) {
  const summary = nbaSlateSummary(games)
  return <section className="page-head__stats nfl-slate__stats" aria-label="Day summary">
    <StatChip value={summary.games} label="Games" />
    <StatChip value={summary.propLines} label="Prop lines" />
    <StatChip value={`${summary.finals} / ${summary.games}`} label="Final" />
    <StatChip value={summary.oddsUpdated ?? MISSING} label="Odds updated" />
  </section>
}

function Legend() {
  return <p className="nfl-slate__legend">
    <span><b>Market</b> is DraftKings when stored, else the latest book; win probability is de-vigged.</span>
    <span><b>Gaps</b> are the reference projection minus the line: gray reference, not picks, until the ranking check adopts one.</span>
    <span><b>Scores</b> load the morning after each game.</span>
  </p>
}

export default function NbaSlatePage() {
  const [searchParams] = useSearchParams()
  // A malformed link falls back to the API's choice rather than an error page.
  const requested = parseSlateDate(searchParams.get('date'))
  const slate = useNbaSlate(requested)
  const rows = useMemo(() => {
    const now = new Date()
    return (slate.data?.games ?? []).map(game => nbaSlateRow(game, now))
  }, [slate.data])
  const gaps = useNbaSlateGaps(slate.data?.date ?? null)
  // A failed digest only hides the strip; the games still render.
  const digest = useMemo(() => nbaSlateDigest(gaps.data?.items ?? []), [gaps.data])
  const { query } = useSlateCommand()
  const games = useMemo(() => slate.data?.games ?? [], [slate.data])
  const commandRows = useMemo(
    () => nbaSlateCommandRows(games, gaps.isError ? [] : gaps.data?.items ?? []),
    [games, gaps.data, gaps.isError],
  )
  const commandScope = useMemo(() => slate.isLoading || slate.isError || !slate.data
    ? null
    : { periodKey: slate.data.date, rows: commandRows },
  [commandRows, slate.data, slate.isError, slate.isLoading])
  useRegisterSlateCommand(commandScope)
  const commandActive = normalizeSlateCommand(query).length > 0
  const filteredRows = useMemo(() => {
    if (!commandActive) return rows
    const gameIds = new Set(matchingSlateCommandRows(commandRows, query).map(row => Number(row.path.split('/').at(-1))))
    return rows.filter(row => gameIds.has(row.gameId))
  }, [commandActive, commandRows, query, rows])

  if (slate.isLoading) return <LoadingState message="Loading NBA slate..." />
  if (slate.isError || !slate.data) return <ErrorState error={slate.error} onRetry={() => void slate.refetch()} />
  const { date, previousDate, nextDate } = slate.data
  const datePath = (target: string | null) => target && `/nba?date=${target}`
  return <div className="page-shell nfl-slate nba-slate"><div className="page-container is-wide">
    <PageHead
      title="NBA slate"
      meta={slateDateLabel(date)}
      period={{ label: 'Slate date', previous: datePath(previousDate), next: datePath(nextDate) }}
      stats={games.length > 0 && <Summary games={games} />}
    />
    {games.length === 0 ? <div className="nfl-empty">No NBA games on this date.</div> : <>
      <NbaSlateDigest items={digest} />
      <Legend />
      <section className="nfl-slate-window" aria-label="Games">
        {commandActive && filteredRows.length === 0
          ? <div className="nfl-empty">No games found for this slate search.</div>
          : <NbaSlateTable rows={filteredRows} />}
      </section>
    </>}
  </div></div>
}
