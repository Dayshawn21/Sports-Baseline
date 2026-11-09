import { useMemo } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { NhlSlateTable } from '~/components/nhl/NhlSlateTable'
import ErrorState from '~/components/shared/ErrorState'
import LoadingState from '~/components/shared/LoadingState'
import PageHead from '~/components/shared/PageHead'
import SlateDatePicker from '~/components/shared/SlateDatePicker'
import SlateLegend from '~/components/shared/SlateLegend'
import { useRegisterSlateCommand, useSlateCommand } from '~/components/shared/SlateCommandProvider'
import { useNhlSlate } from '~/hooks/useNhl'
import { nhlSlateRow, nhlSlateSummary, parseSlateDate, slateDateLabel } from '~/utils/nhlSlate'
import { matchingSlateCommandRows, nhlSlateCommandRows, normalizeSlateCommand } from '~/utils/slateCommand'
import { SLATE_LEGENDS } from '~/utils/slateLegend'
import { gameSlateLine, startTimes, tableCountPart } from '~/utils/slatePeriod'
import './nfl-slate.css'
import './nhl-slate.css'

export default function NhlSlatePage() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
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

  if (slate.isLoading || slate.isError || !slate.data) return <div className="page-shell nfl-slate nhl-slate"><div className="page-container is-wide">
    <PageHead title="NHL slate" />
    {slate.isLoading ? <LoadingState message="Loading NHL slate..." /> : <ErrorState error={slate.error} onRetry={() => void slate.refetch()} />}
  </div></div>
  const { date, previousDate, nextDate } = slate.data
  const line = gameSlateLine(slateDateLabel(date), nhlSlateSummary(games), startTimes(games.map(game => game.startUtc)), Date.now())
  const datePath = (target: string | null) => target === null ? null : `/nhl?date=${target}`
  return <div className="page-shell nfl-slate nhl-slate"><div className="page-container is-wide">
    <PageHead title="NHL slate" meta={line}
      period={{
        label: 'Slate date', previous: datePath(previousDate), next: datePath(nextDate),
        picker: <SlateDatePicker date={date} onPick={picked => { if (picked) navigate(`/nhl?date=${picked}`) }} />,
      }} />
    {games.length === 0 ? <div className="nfl-empty">
      No NHL games on {slateDateLabel(date)}.{' '}
      {nextDate && <Link className="nfl-empty__next" to={`/nhl?date=${nextDate}`}>Next slate: {slateDateLabel(nextDate)} →</Link>}
    </div> : <>
      <SlateLegend {...SLATE_LEGENDS.nhl} />
      <section className="nfl-slate-window" aria-label="Games">
        <h2 className="nfl-slate-window__title">All games <small>{tableCountPart(filtered.length, rows.length, searchActive, 'game')}</small></h2>
        {searchActive && filtered.length === 0 ? <div className="nfl-empty">No games found for this slate search.</div> : <NhlSlateTable rows={filtered} />}
      </section>
    </>}
  </div></div>
}
