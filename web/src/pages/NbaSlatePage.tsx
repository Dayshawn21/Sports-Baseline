import { useMemo } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { NbaSlateTable } from '~/components/nba/NbaSlateTable'
import ErrorState from '~/components/shared/ErrorState'
import LoadingState from '~/components/shared/LoadingState'
import PageHead from '~/components/shared/PageHead'
import SlateFinalsWindow from '~/components/shared/SlateFinalsWindow'
import SlateLegend from '~/components/shared/SlateLegend'
import SlateDatePicker from '~/components/shared/SlateDatePicker'
import { SlateNoPicks } from '~/components/shared/SlateNoPicks'
import { useRegisterSlateCommand, useSlateCommand } from '~/components/shared/SlateCommandProvider'
import { useNbaSlate, useNbaSlateGaps } from '~/hooks/useNba'
import { usePhoneLayout } from '~/hooks/usePhoneLayout'
import { type NbaSlateDigestItem, type NbaSlateRowModel, nbaSlateDigest, nbaSlateRow, nbaSlateSummary, parseSlateDate, slateDateLabel } from '~/utils/nbaSlate'
import { commandGameContext, matchingSlateCommandRows, nbaSlateCommandRows, normalizeSlateCommand } from '~/utils/slateCommand'
import { slateRemainingLine } from '~/utils/slateHeadline'
import { SLATE_LEGENDS } from '~/utils/slateLegend'
import { finalsStartOpen, openWindowTitle, slatePhase, splitFinals } from '~/utils/slateOrder'
import { gameSlateLine, slatePeriodLine, staleOddsSince, startTimes, tableCountPart, windowOddsNote } from '~/utils/slatePeriod'
import './nfl-slate.css'

function gapLink(item: NbaSlateDigestItem) {
  return {
    key: item.key,
    to: `/nba/game/${item.gameId}`,
    playerName: item.playerName,
    market: item.market,
    gap: item.gap,
    share: item.gapShare,
    ariaLabel: [`${item.playerName}, ${item.market}, ${item.matchup}, gap ${item.gap}`, item.gapScaled, 'open game page'].filter(Boolean).join(', '),
  }
}

/** A search result's second line: tip time, state, or the final score. */
function commandContext(row: NbaSlateRowModel | undefined): string | undefined {
  if (!row) return undefined
  const label = row.state === 'started' || row.state === 'pending' ? row.tags[0] ?? row.tip : row.tip
  return commandGameContext(label, row.state === 'final' ? row : undefined)
}

export default function NbaSlatePage() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  // A malformed link falls back to the API's choice rather than an error page.
  const requested = parseSlateDate(searchParams.get('date'))
  const slate = useNbaSlate(requested)
  const { rows, staleSince, nowMs } = useMemo(() => {
    const now = new Date()
    const all = slate.data?.games ?? []
    // The period line's own check: while the odds are stale, a row shows its age only when it differs from the head's.
    const stale = staleOddsSince(nbaSlateSummary(all).oddsUpdatedMs, startTimes(all.map(game => game.startUtc)), now.getTime())
    return { rows: all.map(game => nbaSlateRow(game, now, stale)), staleSince: stale, nowMs: now.getTime() }
  }, [slate.data])
  const staleOdds = staleSince !== null
  const gaps = useNbaSlateGaps(slate.data?.date ?? null)
  // A failed digest only hides the strip; the games still render.
  const digest = useMemo(() => nbaSlateDigest(gaps.data?.items ?? []), [gaps.data])
  const remaining = useMemo(() => slateRemainingLine(
    (slate.data?.games ?? []).map((game, index) => ({ state: rows[index]?.state ?? 'upcoming', startUtc: game.startUtc })), Date.now(),
  ), [rows, slate.data])
  const { query } = useSlateCommand()
  const phone = usePhoneLayout()
  const games = useMemo(() => slate.data?.games ?? [], [slate.data])
  const commandRows = useMemo(
    () => nbaSlateCommandRows(games.map((game, index) => ({ ...game, commandContext: commandContext(rows[index]) })), gaps.isError ? [] : gaps.data?.items ?? []),
    [games, gaps.data, gaps.isError, rows],
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
  // Display order only: games in play, then upcoming, then postponed; finals go to one closed window at the end.
  const split = useMemo(() => splitFinals(rows, row => slatePhase(row.state)), [rows])
  const shown = useMemo(() => splitFinals(filteredRows, row => slatePhase(row.state)), [filteredRows])

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
      <SlateNoPicks
        sport="nba" remaining={remaining} gaps={digest.map(gapLink)}
        gapsLabel="Largest gaps" gapsOrder="by share of the line"
      />
      {!phone && <SlateLegend {...SLATE_LEGENDS.nba} />}
      {(shown.open.length > 0 || (commandActive && filteredRows.length === 0)) && <section className="nfl-slate-window" aria-label="Games">
        <h2 className="nfl-slate-window__title">{openWindowTitle(split.finals.length)} <small>{slatePeriodLine([
          tableCountPart(shown.open.length, split.open.length, commandActive, 'game'),
          windowOddsNote(staleSince, shown.open.map(row => slatePhase(row.state)), nowMs),
        ])}</small></h2>
        {commandActive && filteredRows.length === 0
          ? <div className="nfl-empty">No games found for this slate search.</div>
          : shown.open.length > 0 && <NbaSlateTable rows={shown.open} staleOdds={staleOdds} />}
      </section>}
      {shown.finals.length > 0 && <SlateFinalsWindow
        key={`${date}-${commandActive}`}
        subtitle={tableCountPart(shown.finals.length, split.finals.length, commandActive, 'game')}
        startOpen={finalsStartOpen(split.open.length, commandActive)}
      >
        <NbaSlateTable label="Final games" rows={shown.finals} />
      </SlateFinalsWindow>}
      {phone && <SlateLegend {...SLATE_LEGENDS.nba} />}
    </>}
  </div></div>
}
