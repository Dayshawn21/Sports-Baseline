import { useMemo, useState } from 'react'
import { DatePicker, Select } from 'antd'
import { useTennisToday } from '~/hooks/useTennisToday'
import { useBestPicks } from '~/hooks/useBestPicks'
import { useAdminView } from '~/hooks/useAdmin'
import { useBetProps, useDKProps, usePrizePicksProps } from '~/hooks/useProps'
import LoadingState from '~/components/shared/LoadingState'
import PageHead from '~/components/shared/PageHead'
import TennisSlateSummary from '~/components/tennis/TennisSlateSummary'
import TennisSlateDigest from '~/components/tennis/TennisSlateDigest'
import TennisSlateTable from '~/components/tennis/TennisSlateTable'
import { useRegisterSlateCommand, useSlateCommand } from '~/components/shared/SlateCommandProvider'
import type { PropsHealth, UnifiedSort } from '~/utils/unifiedTennis'
import {
  UNIFIED_SORT_OPTIONS,
  assessPropsHealth,
  bestBetPicks,
  composeUnifiedMatches,
} from '~/utils/unifiedTennis'
import type { TourTab } from '~/utils/tennisSlate'
import { featuredPicks, isGroupedSort, revealTab, slateRows, tennisDigest } from '~/utils/tennisSlate'
import { slateDateLabel } from '~/utils/nbaSlate'
import { matchingSlateCommandRows, normalizeSlateCommand, tennisSlateCommandRows } from '~/utils/slateCommand'
import '~/components/tennis/tennis-slate.css'

type PropSource = 'prizepicks' | 'dk' | 'bet'

const SOURCE_OPTIONS = [
  { value: 'prizepicks', label: 'PrizePicks' },
  { value: 'dk', label: 'DraftKings' },
  { value: 'bet', label: 'Bet365' },
]

function SourceNotice({ label, onRetry }: { label: string; onRetry: () => void }) {
  return (
    <div className="unified-source-notice" role="alert">
      <span>{label} could not be loaded. Available picks are still shown.</span>
      <button type="button" onClick={onRetry}>Retry</button>
    </div>
  )
}

/**
 * A props response can succeed and still be unusable — unlinked props lose their
 * confidence upstream, so the page would otherwise show a clean `0` for what is
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
            linked to a match and {scored.toLocaleString()} have a confidence rating. Prop rows are
            mostly unavailable — this is a data pipeline issue, not an empty slate.
          </>
        )}
      </span>
    </div>
  )
}

export default function TennisIntelligencePage() {
  const [tour, setTour] = useState<string | undefined>()
  const [date, setDate] = useState<string | undefined>()
  const [sort, setSort] = useState<UnifiedSort>('opportunity')
  const [upcomingOnly, setUpcomingOnly] = useState(true)
  const [showLeans, setShowLeans] = useState(false)
  const adminView = useAdminView()
  const [chosenSource, setSource] = useState<PropSource>('prizepicks')
  // Visitors get PrizePicks only: the book switch and its health warning are owner diagnostics.
  const source: PropSource = adminView ? chosenSource : 'prizepicks'
  const [expandedKey, setExpandedKey] = useState<string | null>(null)
  const [tourTab, setTourTab] = useState<TourTab>('all')
  const { query } = useSlateCommand()

  const predictionsQuery = useTennisToday({ tour, date })
  const bestPicksQuery = useBestPicks({ tour, date })
  const prizePicksQuery = usePrizePicksProps()
  const draftKingsQuery = useDKProps(source === 'dk')
  const betOnlineQuery = useBetProps(source === 'bet')
  const propsQuery = source === 'dk'
    ? draftKingsQuery
    : source === 'bet'
      ? betOnlineQuery
      : prizePicksQuery
  const sourceLabel = SOURCE_OPTIONS.find((option) => option.value === source)?.label ?? 'Props'

  const matches = useMemo(() => composeUnifiedMatches(
    predictionsQuery.data?.matches ?? [],
    bestPicksQuery.data?.matches ?? [],
    propsQuery.data?.props ?? [],
    { showLeans, upcomingOnly, tour, date, sort },
  ), [
    predictionsQuery.data?.matches,
    bestPicksQuery.data?.matches,
    propsQuery.data?.props,
    showLeans,
    upcomingOnly,
    tour,
    date,
    sort,
  ])

  const counts = useMemo(() => {
    let props = 0
    let locks = 0
    let strongOrBetter = 0
    for (const match of matches) {
      const picks = bestBetPicks(match)
      props += match.props.length
      for (const item of [...match.props, ...picks]) {
        if (item.confidence === 'LOCK') locks += 1
        if (item.confidence === 'LOCK' || item.confidence === 'STRONG') strongOrBetter += 1
      }
    }
    return { props, locks, strongOrBetter }
  }, [matches])

  const digest = useMemo(() => tennisDigest(featuredPicks(matches, 4)), [matches])
  const rows = useMemo(() => slateRows(matches), [matches])

  // Predictions and Best Picks are the primary sources; gating on props too
  // would let a fast props failure render the empty state mid-load.
  const primaryLoading = predictionsQuery.isLoading || bestPicksQuery.isLoading
  const commandRows = useMemo(() => tennisSlateCommandRows(rows), [rows])
  const commandScope = useMemo(() => primaryLoading ? null : ({
    periodKey: JSON.stringify({ date, tour, source, upcomingOnly, showLeans, sort }),
    rows: commandRows,
  }), [commandRows, date, primaryLoading, showLeans, sort, source, tour, upcomingOnly])
  useRegisterSlateCommand(commandScope)

  const commandActive = normalizeSlateCommand(query).length > 0
  const filteredRows = useMemo(() => {
    if (!commandActive) return rows
    const matchingKeys = new Set(matchingSlateCommandRows(commandRows, query).map(row => row.key))
    return rows.filter(row => matchingKeys.has(row.key))
  }, [commandActive, commandRows, query, rows])

  function toggleRow(matchKey: string) {
    setExpandedKey((open) => (open === matchKey ? null : matchKey))
  }

  // A digest pick opens its row (never closes it), then brings the row to the reader once it renders.
  function openFromDigest(matchKey: string) {
    setTourTab(revealTab(rows, matchKey, tourTab))
    setExpandedKey(matchKey)
    requestAnimationFrame(() => {
      const toggle = document.querySelector<HTMLButtonElement>(`[data-match-key="${CSS.escape(matchKey)}"]`)
      toggle?.focus({ preventScroll: true })
      toggle?.closest('tr')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    })
  }

  const propsHealth = useMemo(
    () => assessPropsHealth(propsQuery.data?.props ?? []),
    [propsQuery.data?.props],
  )

  return (
    <div className="page-shell">
      <div className="page-container is-wide unified-tennis-page">
        <PageHead
          title="Tennis slate"
          meta={date ? slateDateLabel(date) : 'Today and tomorrow'}
          actions={
            <div className="filter-bar-responsive unified-filters">
              <button
                type="button"
                className={`unified-filter-button${upcomingOnly ? ' is-active' : ''}`}
                aria-pressed={upcomingOnly}
                onClick={() => setUpcomingOnly((value) => !value)}
              >
                Upcoming only
              </button>
              <Select
                aria-label="Tour"
                placeholder="All tours"
                allowClear
                value={tour}
                options={[
                  { value: 'ATP', label: 'ATP' },
                  { value: 'WTA', label: 'WTA' },
                  { value: 'CHALLENGER', label: 'Challenger' },
                ]}
                onChange={setTour}
              />
              <DatePicker
                aria-label="Match date"
                placeholder="Today & tomorrow"
                allowClear
                onChange={(_, value) => setDate((value as string) || undefined)}
              />
              <Select
                aria-label="Sort by"
                value={sort}
                options={UNIFIED_SORT_OPTIONS}
                labelRender={({ label }) => <>Sort: {label}</>}
                onChange={(value) => setSort(value as UnifiedSort)}
              />
              {adminView && (
                <Select
                  aria-label="Prop source"
                  value={source}
                  options={SOURCE_OPTIONS}
                  onChange={(value) => setSource(value as PropSource)}
                />
              )}
              <button
                type="button"
                className={`unified-filter-button${showLeans ? ' is-active is-lean' : ''}`}
                aria-pressed={showLeans}
                onClick={() => setShowLeans((value) => !value)}
              >
                {showLeans ? 'Hide Leans' : 'Show Leans'}
              </button>
            </div>
          }
          stats={!primaryLoading && (
            <TennisSlateSummary
              matches={matches.length}
              props={counts.props}
              locks={counts.locks}
              strongOrBetter={counts.strongOrBetter}
            />
          )}
        />

        <div className="unified-notices">
          {predictionsQuery.isError && <SourceNotice label="Predictions" onRetry={predictionsQuery.refetch} />}
          {bestPicksQuery.isError && <SourceNotice label="Best Picks" onRetry={bestPicksQuery.refetch} />}
          {propsQuery.isError && <SourceNotice label={sourceLabel} onRetry={propsQuery.refetch} />}
          {adminView && !propsQuery.isError && propsHealth.degraded && (
            <PropsHealthNotice label={sourceLabel} health={propsHealth} />
          )}
        </div>

        {/* One branch only. Rendering the grid while predictions are still in
            flight would show prop-linked matches as "Prediction unavailable"
            and then reshuffle them once predictions land. */}
        {primaryLoading ? (
          <LoadingState message="Finding the best opportunities..." />
        ) : matches.length === 0 ? (
          <div className="unified-empty-state">
            <div className="unified-empty-title">No Best Bets found</div>
            <p>Try another date or tour{adminView ? ', switch the prop source,' : ''} or include Lean picks.</p>
            {!showLeans && <button type="button" onClick={() => setShowLeans(true)}>Show Leans</button>}
          </div>
        ) : (
          <>
          <TennisSlateDigest items={digest} selectedKey={expandedKey} onSelect={openFromDigest} />
          <TennisSlateTable
            rows={filteredRows}
            grouped={isGroupedSort(sort)}
            expandedKey={expandedKey}
            onToggle={toggleRow}
            showFlags={adminView}
            tab={tourTab}
            onTabChange={setTourTab}
            searchAllTabs={commandActive}
            emptyMessage={commandActive ? 'No matches found for this slate search.' : undefined}
          />
          </>
        )}
      </div>
    </div>
  )
}
