import type { NflGameOdds, NflHistorySample, NflSlateGame, NflSlateLine } from '~/types/nfl'
import { bookLabel } from '~/utils/matchOdds'
import { depthLabel, injuryLabel } from '~/utils/nflAvailability'
import { nflBookOddsEvidence, type NflBookOddsEvidence } from '~/utils/nflBookOdds'
import { nflGameModelSummary } from '~/utils/nflGameModel'
import {
  BASELINE_REASON_LABELS, FLAG_LABELS, ODDS_TYPE_COLORS, ODDS_TYPE_LABELS, formatHistoryValue, formatKickoffTime,
  formatProjection, marketLabel, matchupAllowedLabel, segmentLabel,
} from '~/utils/nflLabels'
import { teamBadge } from '~/utils/nflPropCards'
import { edgeLabel, overProbabilityLabel, overShareLabel, signalSummary, trustLabel } from '~/utils/nflSignal'
import { snapShareLabel } from '~/utils/nflSnapShare'

export interface NflDetailRow {
  label: string
  value: string
  note: string | null
}

export interface NflDetailHistory {
  title: string
  value: string
  detail: string | null
}

export interface NflDetailLine {
  key: number
  typeLabel: string
  typeColor: string
  lineText: string
  pOverText: string | null
  selected: boolean
}

export interface NflDetailGameMarket {
  book: string
  rows: { label: string, value: string }[]
  modelText: string | null
  modelVersion: string | null
}

export interface NflPropDetailModel {
  badge: string
  playerName: string
  meta: string
  projectionLabel: string
  projectionText: string
  deltaText: string
  isUnder: boolean
  hasEdge: boolean
  recentForm: NflDetailHistory
  context: NflDetailHistory[]
  why: string
  breakdown: NflDetailRow[]
  lines: NflDetailLine[]
  pOverNote: string | null
  sportsbook: NflBookOddsEvidence | null
  gameMarket: NflDetailGameMarket | null
  status: NflDetailRow[]
  flags: { key: string, label: string, tooltip: string }[]
}

function signedPct(value: number): string {
  return `${value > 0 ? '+' : ''}${value.toFixed(1)}%`
}

function signed(value: number, digits: number): string {
  return `${value > 0 ? '+' : ''}${value.toFixed(digits)}`
}

function typeLabel(oddsType: string | null, fallback: string): string {
  return oddsType ? ODDS_TYPE_LABELS[oddsType] ?? oddsType : fallback
}

function history(title: string, market: string, sample: NflHistorySample): NflDetailHistory {
  if (sample.average === null) return { title, value: 'No completed history', detail: null }
  return {
    title,
    value: `${formatProjection(market, sample.average)} avg · ${sample.values.length} games`,
    detail: sample.values.map(item => `${formatHistoryValue(market, item.value)} vs ${item.opponentTeam ?? '--'}`).join(' · '),
  }
}

function meta(row: NflSlateLine, game: NflSlateGame | null): string {
  const parts = [row.position ?? '--', marketLabel(row.market)]
  if (game) parts.push(`${game.awayTeam} @ ${game.homeTeam}`)
  const kickoff = formatKickoffTime(game?.startUtc ?? null)
  if (kickoff) parts.push(kickoff)
  if (row.segment !== 'full_game') parts.push(segmentLabel(row.segment))
  return parts.join(' · ')
}

function deltaText(row: NflSlateLine): string {
  if (row.line === null) return 'No line'
  const line = `${row.line.toFixed(1)} line`
  return row.edge === null ? line : `${edgeLabel(row.edge)} vs ${line}`
}

function breakdown(row: NflSlateLine): NflDetailRow[] {
  const opponent = row.opponentTeam ?? 'Opponent'
  const rows: NflDetailRow[] = [
    { label: 'Baseline', value: `${row.gamesInSample} games · ${row.baselineSeason ?? 'No season'}`, note: BASELINE_REASON_LABELS[row.baselineReason] ?? null },
    {
      label: 'Matchup',
      value: row.opponentAdjustmentPct === null ? 'Unavailable' : `${opponent} ${signedPct(row.opponentAdjustmentPct)}`,
      note: row.opponentAdjustmentPct === null ? null : matchupAllowedLabel(row.market, row.position, row.opponentPositionAverage, row.opponentSampleGames),
    },
    { label: 'Usage', value: row.usageAdjustmentPct === null ? 'Not applicable' : signedPct(row.usageAdjustmentPct), note: null },
  ]
  const snap = snapShareLabel(row)
  if (snap !== null) rows.push({ label: 'Snap share', value: snap, note: null })
  rows.push({ label: 'Projection', value: formatProjection(row.market, row.projection), note: null })
  return rows
}

function lines(row: NflSlateLine, alternates: NflSlateLine[]): NflDetailLine[] {
  const item = (line: NflSlateLine, selected: boolean): NflDetailLine => ({
    key: line.lineId,
    typeLabel: typeLabel(line.oddsType, selected ? 'Standard' : 'Alternate'),
    typeColor: ODDS_TYPE_COLORS[line.oddsType ?? ''] ?? 'default',
    lineText: line.line?.toFixed(1) ?? '--',
    pOverText: overShareLabel(line.pOver),
    selected,
  })
  return [item(row, true), ...alternates.map(line => item(line, false))]
}

function moneyline(value: number | null): string {
  return value === null ? '--' : signed(value, 0)
}

function gameMarket(game: NflSlateGame | null): NflDetailGameMarket | null {
  const odds: NflGameOdds | null = game?.odds ?? null
  if (game === null || odds === null) return null
  const model = nflGameModelSummary(game.model, odds, game.homeTeam, game.awayTeam)
  return {
    book: bookLabel(odds.book),
    rows: [
      { label: `${game.awayTeam} ML`, value: moneyline(odds.awayMoneyline) },
      { label: `${game.homeTeam} ML`, value: moneyline(odds.homeMoneyline) },
      { label: 'Spread', value: odds.homeSpread === null ? '--' : `${game.homeTeam} ${signed(odds.homeSpread, 1)}` },
      { label: 'Total', value: odds.total?.toFixed(1) ?? '--' },
    ],
    modelText: model ? `${model.spread.model} · ${model.winProbability.model} · ${model.total.model}` : null,
    modelVersion: game.model?.modelVersion ?? null,
  }
}

function status(row: NflSlateLine): NflDetailRow[] {
  return [
    { label: 'Line shape', value: `${typeLabel(row.oddsType, 'Standard')} · ${segmentLabel(row.segment)}`, note: null },
    { label: 'Injury', value: injuryLabel(row) ?? 'Clear', note: null },
    { label: 'Depth', value: depthLabel(row) ?? 'Not listed', note: null },
    { label: 'Trust', value: trustLabel(row), note: null },
  ]
}

function projectionLabel(market: string): string {
  const label = marketLabel(market)
  return `Projected ${label.charAt(0).toLowerCase()}${label.slice(1)}`
}

/** What the prop detail panel shows for one line; every string is one the old evidence panel rendered, except the game market. */
export function nflPropDetail(row: NflSlateLine, game: NflSlateGame | null, alternates: NflSlateLine[], now: number): NflPropDetailModel {
  const opponent = row.opponentTeam ?? 'Opponent'
  const group = row.position ? `${row.position}s` : 'the position'
  const adjustment = row.opponentAdjustmentPct === null ? '' : ` Opponent adjustment: ${signedPct(row.opponentAdjustmentPct)}.`
  return {
    badge: game ? teamBadge(row, game.awayTeam, game.homeTeam) : row.position ?? '--',
    playerName: row.playerName,
    meta: meta(row, game),
    projectionLabel: projectionLabel(row.market),
    projectionText: formatProjection(row.market, row.projection),
    deltaText: deltaText(row),
    isUnder: row.edge !== null && row.edge < 0,
    hasEdge: row.edge !== null,
    recentForm: history('Recent form', row.market, row.recentForm),
    context: [
      history(`Vs ${opponent}`, row.market, row.opponentHistory),
      history(`${opponent} allowed to all ${group}, per game · last 5`, row.market, row.opponentAllowedHistory),
    ],
    why: `${signalSummary(row)}.${adjustment}`,
    breakdown: breakdown(row),
    lines: lines(row, alternates),
    pOverNote: overProbabilityLabel(row),
    sportsbook: nflBookOddsEvidence(row, now),
    gameMarket: gameMarket(game),
    status: status(row),
    flags: row.qualityFlags
      .filter(flag => flag !== 'historical_baseline')
      .map(flag => ({ key: flag, label: flag.replaceAll('_', ' '), tooltip: FLAG_LABELS[flag] ?? flag })),
  }
}
