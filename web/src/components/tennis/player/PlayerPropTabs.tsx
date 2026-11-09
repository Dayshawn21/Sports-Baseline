import { useEffect, useMemo } from 'react'
import { useSearchParams } from 'react-router-dom'
import { PlayerMarketTabs } from '~/components/shared/PlayerMarketTabs'
import { TennisMarketPanel } from '~/components/tennis/player/TennisMarketPanel'
import { TennisRecentBars } from '~/components/tennis/TennisPropEvidenceBody'
import { useBestPicks } from '~/hooks/useBestPicks'
import { useDKProps, usePrizePicksProps } from '~/hooks/useProps'
import { usePlayerMatches } from '~/hooks/useTennisPlayer'
import { useTennisToday } from '~/hooks/useTennisToday'
import {
  FORM_PARAM, MARKET_PARAM, MATCH_PARAM, PROP_PARAM, formShortNote, formWindowOptions, formWindowSample, matchOptions, parseTennisFormWindow, playerMarketTabs, resolveFormWindow, tennisTabSearch,
  type FormWindowOption, type PlayerMatchOption, type TennisFormWindow,
} from '~/utils/tennisPlayerProps'
import { buildTennisPropBoard, lineNumber, marketLabel, marketTitle, moneylineBoardRows, winASetBoardRows, type TennisBoardLine } from '~/utils/tennisPropBoard'
import { recentStatBars } from '~/utils/tennisPropCards'
import '~/pages/tennis-prop-board.css'
import './tennis-player-props.css'

const FORM_LOG_LIMIT = 50

interface FormChartProps {
  row: TennisBoardLine
  log: ReturnType<typeof usePlayerMatches>
  window: TennisFormWindow
  option: PlayerMatchOption | null
}

function FormChart({ row, log, window, option }: FormChartProps) {
  const line = lineNumber(row)
  if (log.isLoading) return <section className="tennis-prop-form"><p>Loading recent matches...</p></section>
  if (log.isError || !log.data) return <section className="tennis-prop-form"><p>Recent matches are unavailable.</p></section>
  const sample = formWindowSample(log.data.log, window, option?.opponentId ?? null)
  const bars = line == null ? null : recentStatBars(sample, row.statType, line)
  if (line == null || !bars?.some(bar => bar.value != null)) {
    return <section className="tennis-prop-form"><p>{sample.length === 0 ? 'No completed matches for this window.' : `No recent results to show for ${marketLabel(row.statType)}.`}</p></section>
  }
  const name = window === 'opp' ? `vs ${option?.opponentName ?? 'opponent'}` : `last ${bars.length}`
  const note = formShortNote(window, sample.length)
  return <TennisRecentBars title={`${marketLabel(row.statType)} · ${name}${note ? ` · ${note}` : ''}`} line={line} bars={bars} />
}

interface SegmentOption<T extends string> {
  value: T
  label: string
  disabledReason?: string | null
}

function Segment<T extends string>({ label, options, value, onChange }: { label: string, options: Array<SegmentOption<T>>, value: T, onChange: (value: T) => void }) {
  return <div className="tennis-prop-seg" role="group" aria-label={label}>
    {options.map(option => <button key={option.value} type="button" className={value === option.value ? 'is-selected' : ''} aria-pressed={value === option.value} disabled={Boolean(option.disabledReason)} title={option.disabledReason ?? undefined} onClick={() => onChange(option.value)}>{option.label}</button>)}
  </div>
}

function windowChoices(options: FormWindowOption[]): Array<SegmentOption<TennisFormWindow>> {
  return options.map(option => ({ value: option.window, label: option.label, disabledReason: option.disabledReason }))
}

function useBoardTabs(playerId: number, playerName: string) {
  const predictions = useTennisToday()
  const bestPicks = useBestPicks()
  const prizePicks = usePrizePicksProps()
  const draftKings = useDKProps()
  const matches = predictions.data?.matches
  const tabs = useMemo(() => {
    const props = [
      ...(prizePicks.data?.props ?? []),
      ...(draftKings.data?.props ?? []),
      ...moneylineBoardRows(matches ?? []),
      ...winASetBoardRows(bestPicks.data?.matches ?? []),
    ]
    return playerMarketTabs(buildTennisPropBoard(props, matches ?? [], 'all', 'all'), playerId, playerName)
  }, [prizePicks.data, draftKings.data, matches, bestPicks.data, playerId, playerName])
  return {
    tabs,
    predictions: matches ?? [],
    loading: prizePicks.isLoading || draftKings.isLoading || predictions.isLoading || bestPicks.isLoading,
    allFailed: prizePicks.isError && draftKings.isError,
  }
}

export default function PlayerPropTabs({ playerId, playerName }: { playerId: number, playerName: string }) {
  const [params, setParams] = useSearchParams()
  const { tabs, predictions, loading, allFailed } = useBoardTabs(playerId, playerName)
  const log = usePlayerMatches(playerId, FORM_LOG_LIMIT)
  const heading = <h2 className="nfl-player-section-title">Today's props</h2>
  const propId = params.get(PROP_PARAM)
  const marketParam = params.get(MARKET_PARAM)

  useEffect(() => {
    if (!loading && propId) document.querySelector(`[data-prop-id="${CSS.escape(propId)}"]`)?.scrollIntoView({ block: 'center' })
  }, [loading, propId, marketParam])

  const update = (key: string, value: string | null) => setParams(previous => {
    const next = new URLSearchParams(previous)
    if (value === null) next.delete(key)
    else next.set(key, value)
    return next
  }, { replace: true })

  if (loading) return <section className="tennis-player-props">{heading}<div className="tennis-match-empty">Loading today's props...</div></section>
  if (allFailed) return <section className="tennis-player-props">{heading}<div className="tennis-match-empty">Today's props could not be loaded.</div></section>
  if (tabs.length === 0) return null

  const tab = tabs.find(item => item.market === params.get(MARKET_PARAM)) ?? tabs[0]
  const matches = matchOptions([...tab.rated, ...tab.review], predictions, playerId, playerName)
  const option = matches.find(item => String(item.matchId) === params.get(MATCH_PARAM)) ?? matches[0] ?? null
  const inMatch = (row: TennisBoardLine) => row.matchId === (option?.matchId ?? null)
  const windowOptions = formWindowOptions(log.data?.log ?? [], option?.opponentId ?? null, option?.opponentName ?? null)
  const window = resolveFormWindow(windowOptions, parseTennisFormWindow(params))
  const rated = tab.rated.filter(inMatch)
  const review = tab.review.filter(inMatch)
  const firstLine = rated[0] ?? review[0] ?? null

  return <section className="tennis-player-props" aria-label={`${playerName} props`}>
    <PlayerMarketTabs heading="Today's props" tabs={tabs.map(item => ({ key: item.market, label: marketTitle(item.market) }))}
      selectedIndex={tabs.indexOf(tab)} hrefFor={key => tennisTabSearch(params, key, tabs[0].market)}>
    <TennisMarketPanel market={tab.market} rated={rated} review={review} selectedId={propId} form={<>
      <div className="tennis-player-props__controls">
        {matches.length > 1 && <Segment label="Match" value={String(option?.matchId)} options={matches.map(item => ({ value: String(item.matchId), label: item.opponentName ? `vs ${item.opponentName}` : item.matchup ?? 'Match' }))} onChange={value => update(MATCH_PARAM, value === String(matches[0].matchId) ? null : value)} />}
        <Segment label="Form window" value={window} options={windowChoices(windowOptions)} onChange={value => update(FORM_PARAM, value === '5' ? null : value)} />
      </div>
      {firstLine && <FormChart row={firstLine} log={log} window={window} option={option} />}
    </>} />
    </PlayerMarketTabs>
  </section>
}
