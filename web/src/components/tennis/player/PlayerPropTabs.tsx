import { useEffect, useMemo, type ReactNode } from 'react'
import { useSearchParams } from 'react-router-dom'
import { GameLogBars } from '~/components/nfl/NflPropDetailSections'
import { PlayerMarketTabs } from '~/components/shared/PlayerMarketTabs'
import { SegmentSwitch, type SegmentOption } from '~/components/shared/SegmentSwitch'
import { TennisMarketPanel } from '~/components/tennis/player/TennisMarketPanel'
import { useBestPicks } from '~/hooks/useBestPicks'
import { useDKProps, usePrizePicksProps } from '~/hooks/useProps'
import { usePlayerMatches } from '~/hooks/useTennisPlayer'
import { useTennisToday } from '~/hooks/useTennisToday'
import {
  FORM_PARAM, MARKET_PARAM, MATCH_PARAM, PROP_PARAM, formShortNote, formWindowOptions, formWindowSample, matchOptions, parseTennisFormWindow, playerMarketTabs, resolveFormWindow, tennisFormSample, tennisFormTitle, tennisTabSearch,
  type FormWindowOption, type PlayerMatchOption, type TennisFormWindow,
} from '~/utils/tennisPlayerProps'
import { buildTennisPropBoard, lineNumber, marketLabel, marketTitle, moneylineBoardRows, winASetBoardRows, type TennisBoardLine } from '~/utils/tennisPropBoard'
import { formBarLabel } from '~/utils/nflFormWindow'
import { recentStatBars } from '~/utils/tennisPropCards'
import '~/pages/tennis-prop-board.css'
import './tennis-player-props.css'

const FORM_LOG_LIMIT = 50
/** A tennis season is the calendar year, so a bar's date gains a year only before January. */
const TENNIS_SEASON_START_MONTH = 0

interface FormChartProps {
  row: TennisBoardLine | null
  log: ReturnType<typeof usePlayerMatches>
  window: TennisFormWindow
  option: PlayerMatchOption | null
  /** The match and form-window switches, in the toolbar beside the line legend. */
  controls: ReactNode
}

/** Message, average and bars for one window, before any chart is drawn. */
function formChartContent(row: TennisBoardLine | null, log: FormChartProps['log'], window: TennisFormWindow, option: PlayerMatchOption | null) {
  const line = row ? lineNumber(row) : null
  if (log.isLoading) return { summary: 'Loading recent matches...', line, sample: null }
  if (log.isError || !log.data) return { summary: 'Recent matches are unavailable.', line, sample: null }
  const matches = formWindowSample(log.data.log, window, option?.opponentId ?? null)
  const sample = row && line != null ? tennisFormSample(recentStatBars(matches, row.statType, line) ?? []) : null
  if (!row || sample?.average == null) {
    return { summary: matches.length === 0 ? 'No completed matches for this window' : `No recent ${row ? marketLabel(row.statType).toLowerCase() : 'results'} to show`, line, sample: null }
  }
  const note = formShortNote(window, matches.length)
  return { summary: `${formBarLabel(sample.average)} avg${note ? ` · ${note}` : ''}`, line, sample }
}

/** Recent form in the section every sport's panel uses: heading and average, switches and line legend, then the shared bars. */
function FormChart({ row, log, window, option, controls }: FormChartProps) {
  const { summary, line, sample } = formChartContent(row, log, window, option)
  return <>
    <div className="nfl-prop-detail__section-head"><h3>{tennisFormTitle(window, option?.opponentName ?? null)}</h3><span>{summary}</span></div>
    <div className="nfl-prop-detail__toolbar">
      <div className="tennis-player-props__controls">{controls}</div>
      {sample && line != null && <span className="nfl-prop-detail__legend">Line {formBarLabel(line)}</span>}
    </div>
    {sample && row && line != null && <GameLogBars row={{ market: row.statType, line, segment: 'full_game' }} sample={sample} seasonStartMonth={TENNIS_SEASON_START_MONTH} />}
  </>
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
    <TennisMarketPanel market={tab.market} rated={rated} review={review} selectedId={propId} form={<FormChart row={firstLine} log={log} window={window} option={option} controls={<>
        {matches.length > 1 && <SegmentSwitch label="Match" value={String(option?.matchId)} options={matches.map(item => ({ value: String(item.matchId), label: item.opponentName ? `vs ${item.opponentName}` : item.matchup ?? 'Match' }))} onChange={value => update(MATCH_PARAM, value === String(matches[0].matchId) ? null : value)} />}
        <SegmentSwitch label="Form window" value={window} options={windowChoices(windowOptions)} onChange={value => update(FORM_PARAM, value === '5' ? null : value)} />
      </>} />} />
    </PlayerMarketTabs>
  </section>
}
