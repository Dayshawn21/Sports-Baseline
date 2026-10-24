import { useMemo } from 'react'
import { useSearchParams } from 'react-router-dom'
import { NhlSlateTable } from '~/components/nhl/NhlSlateTable'
import ErrorState from '~/components/shared/ErrorState'
import LoadingState from '~/components/shared/LoadingState'
import PageHead from '~/components/shared/PageHead'
import StatChip from '~/components/shared/StatChip'
import { useRegisterSlateCommand, useSlateCommand } from '~/components/shared/SlateCommandProvider'
import { useNhlSlate } from '~/hooks/useNhl'
import { nhlSlateRow, nhlSlateSummary, parseSlateDate, slateDateLabel } from '~/utils/nhlSlate'
import { matchingSlateCommandRows, nhlSlateCommandRows, normalizeSlateCommand } from '~/utils/slateCommand'
import './nfl-slate.css'
import './nhl-slate.css'

export default function NhlSlatePage() {
  const [searchParams] = useSearchParams()
  const slate = useNhlSlate(parseSlateDate(searchParams.get('date')))
  const { query } = useSlateCommand()
  const games = useMemo(() => slate.data?.games ?? [], [slate.data])
  const rows = useMemo(() => {
    const now = new Date()
    return games.map(game => nhlSlateRow(game, now))
  }, [games])
  const commandRows = useMemo(() => nhlSlateCommandRows(games), [games])
  const scope = useMemo(() => slate.isLoading || slate.isError || !slate.data
    ? null : { periodKey: slate.data.date, rows: commandRows },
  [commandRows, slate.data, slate.isError, slate.isLoading])
  useRegisterSlateCommand(scope)
  const searchActive = normalizeSlateCommand(query).length > 0
  const filtered = useMemo(() => {
    if (!searchActive) return rows
    const ids = new Set(matchingSlateCommandRows(commandRows, query).map(row => Number(row.path.split('/').at(-1))))
    return rows.filter(row => ids.has(row.gameId))
  }, [commandRows, query, rows, searchActive])

  if (slate.isLoading) return <LoadingState message="Loading NHL slate..." />
  if (slate.isError || !slate.data) return <ErrorState error={slate.error} onRetry={() => void slate.refetch()} />
  const { date, previousDate, nextDate } = slate.data
  const summary = nhlSlateSummary(games)
  const datePath = (target: string | null) => target === null ? null : `/nhl?date=${target}`
  return <div className="page-shell nfl-slate nhl-slate"><div className="page-container is-wide">
    <PageHead title="NHL slate" meta={slateDateLabel(date)}
      period={{ label: 'Slate date', previous: datePath(previousDate), next: datePath(nextDate) }}
      stats={games.length > 0 && <section className="page-head__stats nfl-slate__stats" aria-label="Day summary">
        <StatChip value={summary.games} label="Games" /><StatChip value={summary.propLines} label="Prop lines" />
        <StatChip value={`${summary.finals} / ${summary.games}`} label="Final" /><StatChip value={summary.oddsUpdated ?? '--'} label="Odds updated" />
      </section>} />
    {games.length === 0 ? <div className="nfl-empty">No NHL games on this date.</div> : <>
      <p className="nfl-slate__legend"><span>Stored full-game prices include overtime and shootouts.</span>
        <span>Win probability is de-vigged per book.</span><span>Props are line-only. No NHL picks.</span>
        <span>Scores update after games.</span><span>Goalies and injuries are ESPN reports; late changes may be missing.</span></p>
      <section className="nfl-slate-window" aria-label="Games">
        {searchActive && filtered.length === 0 ? <div className="nfl-empty">No games found for this slate search.</div> : <NhlSlateTable rows={filtered} />}
      </section>
    </>}
  </div></div>
}
