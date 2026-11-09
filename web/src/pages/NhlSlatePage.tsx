import { useMemo } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { NhlSlateTable } from '~/components/nhl/NhlSlateTable'
import ErrorState from '~/components/shared/ErrorState'
import LoadingState from '~/components/shared/LoadingState'
import PageHead from '~/components/shared/PageHead'
import SlateDatePicker from '~/components/shared/SlateDatePicker'
import SlateFinalsWindow from '~/components/shared/SlateFinalsWindow'
import SlateLegend from '~/components/shared/SlateLegend'
import { useRegisterSlateCommand, useSlateCommand } from '~/components/shared/SlateCommandProvider'
import { useNhlSlate } from '~/hooks/useNhl'
import { usePhoneLayout } from '~/hooks/usePhoneLayout'
import { nhlSlateRow, nhlSlateSummary, parseSlateDate, slateDateLabel } from '~/utils/nhlSlate'
import { matchingSlateCommandRows, nhlSlateCommandRows, normalizeSlateCommand } from '~/utils/slateCommand'
import { SLATE_LEGENDS } from '~/utils/slateLegend'
import { finalsStartOpen, openWindowTitle, slatePhase, splitFinals } from '~/utils/slateOrder'
import { gameSlateLine, isOddsStale, startTimes, tableCountPart } from '~/utils/slatePeriod'
import './nfl-slate.css'
import './nhl-slate.css'

export default function NhlSlatePage() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const slate = useNhlSlate(parseSlateDate(searchParams.get('date')))
  const { query } = useSlateCommand()
  const phone = usePhoneLayout()
  const games = useMemo(() => slate.data?.games ?? [], [slate.data])
  const rows = useMemo(() => {
    const now = new Date()
    // The period line's own check, so a row shows its odds age exactly when the head says "(stale)".
    const stale = isOddsStale(nhlSlateSummary(games).oddsUpdatedMs, startTimes(games.map(game => game.startUtc)), now.getTime())
    return games.map(game => nhlSlateRow(game, now, stale))
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
  // Display order only: games in play, then upcoming, then postponed; finals go to one closed window at the end.
  const split = useMemo(() => splitFinals(rows, row => slatePhase(row.state)), [rows])
  const shown = useMemo(() => splitFinals(filtered, row => slatePhase(row.state)), [filtered])

  if (slate.isLoading || slate.isError || !slate.data) return <div className="page-shell nfl-slate nhl-slate"><div className="page-container is-wide">
    <PageHead title="NHL slate" />
    {slate.isLoading ? <LoadingState message="Loading NHL slate..." /> : <ErrorState error={slate.error} onRetry={() => void slate.refetch()} />}
  </div></div>
  const { date, previousDate, nextDate } = slate.data
  const line = gameSlateLine(slateDateLabel(date), nhlSlateSummary(games), startTimes(games.map(game => game.startUtc)), Date.now())
  const datePath = (target: string | null) => target === null ? null : `/nhl?date=${target}`
  return <div className="page-shell nfl-slate nhl-slate is-game-slate"><div className="page-container is-wide">
    <PageHead title="NHL slate" meta={line}
      period={{
        label: 'Slate date', previous: datePath(previousDate), next: datePath(nextDate),
        picker: <SlateDatePicker date={date} onPick={picked => { if (picked) navigate(`/nhl?date=${picked}`) }} />,
      }} />
    {games.length === 0 ? <div className="nfl-empty">
      No NHL games on {slateDateLabel(date)}.{' '}
      {nextDate && <Link className="nfl-empty__next" to={`/nhl?date=${nextDate}`}>Next slate: {slateDateLabel(nextDate)} →</Link>}
    </div> : <>
      {!phone && <SlateLegend {...SLATE_LEGENDS.nhl} />}
      {(shown.open.length > 0 || (searchActive && filtered.length === 0)) && <section className="nfl-slate-window" aria-label="Games">
        <h2 className="nfl-slate-window__title">{openWindowTitle(split.finals.length)} <small>{tableCountPart(shown.open.length, split.open.length, searchActive, 'game')}</small></h2>
        {searchActive && filtered.length === 0 ? <div className="nfl-empty">No games found for this slate search.</div>
          : shown.open.length > 0 && <NhlSlateTable rows={shown.open} />}
      </section>}
      {shown.finals.length > 0 && <SlateFinalsWindow
        key={`${date}-${searchActive}`}
        subtitle={tableCountPart(shown.finals.length, split.finals.length, searchActive, 'game')}
        startOpen={finalsStartOpen(split.open.length, searchActive)}
      >
        <NhlSlateTable label="Final games" rows={shown.finals} />
      </SlateFinalsWindow>}
      {phone && <SlateLegend {...SLATE_LEGENDS.nhl} />}
    </>}
  </div></div>
}
