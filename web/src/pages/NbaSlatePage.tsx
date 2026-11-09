import { useMemo } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { NbaSlateDigest } from '~/components/nba/NbaSlateDigest'
import { NbaSlateTable } from '~/components/nba/NbaSlateTable'
import ErrorState from '~/components/shared/ErrorState'
import LoadingState from '~/components/shared/LoadingState'
import PageHead from '~/components/shared/PageHead'
import SlateLegend from '~/components/shared/SlateLegend'
import SlateDatePicker from '~/components/shared/SlateDatePicker'
import { useRegisterSlateCommand, useSlateCommand } from '~/components/shared/SlateCommandProvider'
import { useNbaSlate, useNbaSlateGaps } from '~/hooks/useNba'
import { usePhoneLayout } from '~/hooks/usePhoneLayout'
import { nbaSlateDigest, nbaSlateRow, nbaSlateSummary, parseSlateDate, slateDateLabel } from '~/utils/nbaSlate'
import { matchingSlateCommandRows, nbaSlateCommandRows, normalizeSlateCommand } from '~/utils/slateCommand'
import { SLATE_LEGENDS } from '~/utils/slateLegend'
import { gameSlateLine, startTimes, tableCountPart } from '~/utils/slatePeriod'
import './nfl-slate.css'

export default function NbaSlatePage() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
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
  const phone = usePhoneLayout()
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

  // The title stays put while the slate loads or fails, as NFL's and tennis's do.
  if (slate.isLoading || slate.isError || !slate.data) return <div className="page-shell nfl-slate nba-slate"><div className="page-container is-wide">
    <PageHead title="NBA slate" />
    {slate.isLoading ? <LoadingState message="Loading NBA slate..." /> : <ErrorState error={slate.error} onRetry={() => void slate.refetch()} />}
  </div></div>
  const { date, previousDate, nextDate } = slate.data
  const datePath = (target: string | null) => target && `/nba?date=${target}`
  const line = gameSlateLine(slateDateLabel(date), nbaSlateSummary(games), startTimes(games.map(game => game.startUtc)), Date.now())
  return <div className="page-shell nfl-slate nba-slate is-game-slate"><div className="page-container is-wide">
    <PageHead
      title="NBA slate"
      meta={line}
      period={{
        label: 'Slate date',
        previous: datePath(previousDate),
        next: datePath(nextDate),
        picker: <SlateDatePicker date={date} onPick={picked => { if (picked) navigate(`/nba?date=${picked}`) }} />,
      }}
    />
    {games.length === 0 ? <div className="nfl-empty">
      No NBA games on {slateDateLabel(date)}.{' '}
      {nextDate && <Link className="nfl-empty__next" to={`/nba?date=${nextDate}`}>Next slate: {slateDateLabel(nextDate)} →</Link>}
    </div> : <>
      <NbaSlateDigest items={digest} />
      {!phone && <SlateLegend {...SLATE_LEGENDS.nba} />}
      <section className="nfl-slate-window" aria-label="Games">
        <h2 className="nfl-slate-window__title">All games <small>{tableCountPart(filteredRows.length, rows.length, commandActive, 'game')}</small></h2>
        {commandActive && filteredRows.length === 0
          ? <div className="nfl-empty">No games found for this slate search.</div>
          : <NbaSlateTable rows={filteredRows} />}
      </section>
      {phone && <SlateLegend {...SLATE_LEGENDS.nba} />}
    </>}
  </div></div>
}
