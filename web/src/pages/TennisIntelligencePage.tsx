import { useMemo, useState, type ReactNode } from 'react'
import { Select } from 'antd'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { useTennisToday } from '~/hooks/useTennisToday'
import { useBestPicks } from '~/hooks/useBestPicks'
import { useAdminView } from '~/hooks/useAdmin'
import { useDKProps, usePrizePicksProps } from '~/hooks/useProps'
import { usePhoneLayout } from '~/hooks/usePhoneLayout'
import LoadingState from '~/components/shared/LoadingState'
import PageHead from '~/components/shared/PageHead'
import SlateDatePicker from '~/components/shared/SlateDatePicker'
import SlateLegend from '~/components/shared/SlateLegend'
import TennisSlateDigest from '~/components/tennis/TennisSlateDigest'
import TennisSlateTable from '~/components/tennis/TennisSlateTable'
import { useRegisterSlateCommand, useSlateCommand } from '~/components/shared/SlateCommandProvider'
import type { PropsHealth, UnifiedSort } from '~/utils/unifiedTennis'
import { assessPropsHealth, composeUnifiedMatches } from '~/utils/unifiedTennis'
import type { TourTab } from '~/utils/tennisSlate'
import { featuredPicks, isGroupedSort, leanDigest, slateRows, tennisDigest } from '~/utils/tennisSlate'
import { ctDayKey } from '~/utils/format'
import { parseSlateDate, slateDateLabel } from '~/utils/slateDates'
import { tennisLegend } from '~/utils/slateLegend'
import { countPart, slatePeriodLine } from '~/utils/slatePeriod'
import { defaultTennisDay, tennisDateNeighbors } from '~/utils/tennisDates'
import { matchingSlateCommandRows, normalizeSlateCommand, tennisSlateCommandRows } from '~/utils/slateCommand'
import '~/components/tennis/tennis-slate.css'

type PropSource = 'prizepicks' | 'dk'

const SOURCE_OPTIONS = [
  { value: 'prizepicks', label: 'PrizePicks' },
  { value: 'dk', label: 'DraftKings' },
]

// Start time is the slate's only order (57d), which keeps its tournament headers.
const SLATE_SORT: UnifiedSort = 'start'

function SourceNotice({ label, onRetry }: { label: string; onRetry: () => void }) {
  return (
    <div className="unified-source-notice" role="alert">
      <span>{label} could not be loaded. Other rows are still shown.</span>
      <button type="button" onClick={onRetry}>Retry</button>
    </div>
  )
}

/**
 * A props response can succeed and still be unusable — unlinked props lose their
 * side upstream, so the page would otherwise show a clean `0` for what is
 * actually a broken pipeline.
 */
function PropsHealthNotice({ label, health }: { label: string; health: PropsHealth }) {
  const { total, linked, scored, reason } = health
  return (
    <div className="unified-source-notice is-warning" role="status">
      <span>
        {reason === 'unsupported' ? (
          <>
            {label} returned {total.toLocaleString()} market{total === 1 ? '' : 's'}, but they are
            match-level lines (spreads/handicaps) that the player-prop model does not score.
            Prop rows are unavailable for this source — try PrizePicks.
          </>
        ) : (
          <>
            {total.toLocaleString()} {label} props loaded, but only {linked.toLocaleString()} are
            linked to a match and {scored.toLocaleString()} have a projected P(over). Prop rows are
            mostly unavailable — this is a data pipeline issue, not an empty slate.
          </>
        )}
      </span>
    </div>
  )
}

export default function TennisIntelligencePage() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const date = parseSlateDate(searchParams.get('date')) ?? undefined
  // No date (or an invalid one) loads today and tomorrow CT, then opens on one of them.
  const today = ctDayKey(Date.now())
  const candidateDays = date ? undefined : [today, tennisDateNeighbors(today).next]
  const adminView = useAdminView()
  const [chosenSource, setSource] = useState<PropSource>('prizepicks')
  // Visitors get PrizePicks only: the book switch and its health warning are owner diagnostics.
  const source: PropSource = adminView ? chosenSource : 'prizepicks'
  const [tourTab, setTourTab] = useState<TourTab>('all')
  const { query } = useSlateCommand()
  const phone = usePhoneLayout()

  const predictionsQuery = useTennisToday({ date, days: candidateDays })
  const bestPicksQuery = useBestPicks({ date, days: candidateDays })
  const prizePicksQuery = usePrizePicksProps()
  const draftKingsQuery = useDKProps(source === 'dk')
  const propsQuery = source === 'dk' ? draftKingsQuery : prizePicksQuery
  const sourceLabel = SOURCE_OPTIONS.find((option) => option.value === source)?.label ?? 'Props'

  const day = useMemo(() => date ?? defaultTennisDay([
    ...(predictionsQuery.data?.matches ?? []),
    ...(bestPicksQuery.data?.matches ?? []),
  ].map(match => match.startUtc), Date.now()), [bestPicksQuery.data?.matches, date, predictionsQuery.data?.matches])

  // Every lean shows (57d), and the day lists all its matches, started ones included, as NBA and NHL do.
  const matches = useMemo(() => composeUnifiedMatches(
    predictionsQuery.data?.matches ?? [],
    bestPicksQuery.data?.matches ?? [],
    propsQuery.data?.props ?? [],
    { showLeans: true, upcomingOnly: false, date: day, sort: SLATE_SORT },
  ), [
    predictionsQuery.data?.matches,
    bestPicksQuery.data?.matches,
    propsQuery.data?.props,
    day,
  ])

  const propCount = useMemo(() => matches.reduce((sum, match) => sum + match.props.length, 0), [matches])

  const digest = useMemo(() => tennisDigest(featuredPicks(matches, 4)), [matches])
  const rows = useMemo(() => slateRows(matches), [matches])
  const leans = useMemo(() => leanDigest(rows, Date.now(), 4), [rows])

  // Predictions and Best Picks are the primary sources; gating on props too
  // would let a fast props failure render the empty state mid-load.
  const primaryLoading = predictionsQuery.isLoading || bestPicksQuery.isLoading
  const commandRows = useMemo(() => tennisSlateCommandRows(rows), [rows])
  const commandScope = useMemo(() => primaryLoading ? null : ({
    periodKey: JSON.stringify({ day, source }),
    rows: commandRows,
  }), [commandRows, day, primaryLoading, source])
  useRegisterSlateCommand(commandScope)

  const commandActive = normalizeSlateCommand(query).length > 0
  const filteredRows = useMemo(() => {
    if (!commandActive) return rows
    const matchingKeys = new Set(matchingSlateCommandRows(commandRows, query).map(row => row.key))
    return rows.filter(row => matchingKeys.has(row.key))
  }, [commandActive, commandRows, query, rows])

  const propsHealth = useMemo(
    () => assessPropsHealth(propsQuery.data?.props ?? []),
    [propsQuery.data?.props],
  )

  // The admin picks the prop source in the legend's Props part; visitors read "PrizePicks" there.
  const legend = tennisLegend(sourceLabel)
  const legendParts: { label: string, text: ReactNode }[] = adminView
    ? legend.parts.map(part => part.label !== 'Props' ? part : {
      ...part,
      text: <Select
        aria-label="Prop source"
        size="small"
        variant="borderless"
        value={source}
        options={SOURCE_OPTIONS}
        onChange={(value) => setSource(value as PropSource)}
        popupMatchSelectWidth={false}
      />,
    })
    : legend.parts

  const periodLabel = slateDateLabel(day)
  const neighbors = tennisDateNeighbors(day)
  const datePath = (target: string | null) => target ? `/tennis?date=${target}` : '/tennis'

  return (
    <div className="page-shell">
      <div className="page-container is-wide unified-tennis-page">
        <PageHead
          title="Tennis slate"
          meta={primaryLoading ? periodLabel : slatePeriodLine([
            periodLabel,
            countPart(matches.length, 'match', 'matches'),
            propCount > 0 && countPart(propCount, 'player prop'),
          ])}
          period={{
            label: 'Slate date',
            previous: datePath(neighbors.previous),
            next: datePath(neighbors.next),
            picker: <SlateDatePicker
              date={day}
              onPick={picked => navigate(datePath(picked))}
            />,
          }}
        />

        <div className="unified-notices">
          {predictionsQuery.isError && <SourceNotice label="Predictions" onRetry={predictionsQuery.refetch} />}
          {bestPicksQuery.isError && <SourceNotice label="Model leans" onRetry={bestPicksQuery.refetch} />}
          {propsQuery.isError && <SourceNotice label={sourceLabel} onRetry={propsQuery.refetch} />}
          {adminView && !propsQuery.isError && propsHealth.degraded && (
            <PropsHealthNotice label={sourceLabel} health={propsHealth} />
          )}
        </div>

        {/* One branch only. Rendering the grid while predictions are still in
            flight would show prop-linked matches as "Prediction unavailable"
            and then reshuffle them once predictions land. */}
        {primaryLoading ? (
          <LoadingState message="Loading tennis slate..." />
        ) : matches.length === 0 ? (
          <div className="nfl-empty">
            No tennis matches on {slateDateLabel(day)}.{' '}
            {adminView && 'Try switching the prop source. '}
            {neighbors.next && <Link className="nfl-empty__next" to={datePath(neighbors.next)}>Next slate: {slateDateLabel(neighbors.next)} →</Link>}
          </div>
        ) : (
          <>
          <TennisSlateDigest priced={digest} leans={leans} />
          {!phone && <SlateLegend parts={legendParts} pick={legend.pick} />}
          <TennisSlateTable
            rows={filteredRows}
            grouped={isGroupedSort(SLATE_SORT)}
            showFlags={adminView}
            tab={tourTab}
            onTabChange={setTourTab}
            searchAllTabs={commandActive}
            total={rows.length}
            emptyMessage={commandActive ? 'No matches found for this slate search.' : undefined}
          />
          {phone && <SlateLegend parts={legendParts} pick={legend.pick} />}
          </>
        )}
      </div>
    </div>
  )
}
