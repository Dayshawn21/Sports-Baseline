import { depthLabel, injuryTag, type InjuryTag } from '~/utils/nflAvailability'
import { nflBookOddsEvidence } from '~/utils/nflBookOdds'
import { formatKickoffTime, formatProjection, marketLabel, segmentLabel } from '~/utils/nflLabels'
import { edgeShare, isConfidentSample, type NflBoardLine } from '~/utils/nflPropBoard'
import { edgeLabel, edgePctLabel, signalSummary, trustLabel } from '~/utils/nflSignal'
import { snapShareLabel } from '~/utils/nflSnapShare'

const TD_MARKET = 'anytime_touchdown'
const DEPTH_FLAGS = ['depth_promoted', 'depth_demoted', 'depth_new']

export interface NflPropCardModel {
  key: number
  kind: 'stat' | 'td'
  rank: number | null
  playerName: string
  badge: string
  meta: string
  unit: string
  lineText: string
  modelText: string
  pickLabel: 'OVER' | 'UNDER' | '--'
  isUnder: boolean
  edgeShareText: string
  edgeText: string
  trust: string
  sampleText: string
  thin: boolean
  injury: InjuryTag | null
  depthText: string | null
  flags: string[]
  why: string
  bookText: string | null
  snapText: string | null
}

export interface NflRecentBar {
  value: number
  opponentTeam: string | null
  heightPct: number
  vsLine: 'above' | 'below' | 'push' | null
}

export interface NflRecentBars {
  bars: NflRecentBar[]
  /** Where the line sits on the same 0-100 scale; null without a line or bars. */
  linePct: number | null
}

export function pickLabel(edge: number | null): NflPropCardModel['pickLabel'] {
  if (edge === null) return '--'
  return edge > 0 ? 'OVER' : 'UNDER'
}

/** The player's own team is whichever side of the game the opponent is not; unknown falls back to the position. */
export function teamBadge(row: Pick<NflBoardLine, 'opponentTeam' | 'position'>, awayTeam: string, homeTeam: string): string {
  if (row.opponentTeam === homeTeam) return awayTeam
  if (row.opponentTeam === awayTeam) return homeTeam
  return row.position ?? '--'
}

function meta(row: NflBoardLine): string {
  const kickoff = formatKickoffTime(row.startUtc)
  const parts = [row.position ?? '--', `${row.awayTeam} @ ${row.homeTeam}`]
  if (kickoff) parts.push(kickoff)
  if (row.segment !== 'full_game') parts.push(segmentLabel(row.segment))
  return parts.join(' · ')
}

export function nflPropCard(row: NflBoardLine, rank: number | null, referenceLine: number | null, now: number): NflPropCardModel {
  const td = row.market === TD_MARKET
  const confident = isConfidentSample(row)
  return {
    key: row.lineId,
    kind: td ? 'td' : 'stat',
    rank,
    playerName: row.playerName,
    badge: teamBadge(row, row.awayTeam, row.homeTeam),
    meta: meta(row),
    unit: marketLabel(row.market).toLowerCase(),
    lineText: row.line?.toFixed(1) ?? '--',
    modelText: formatProjection(row.market, row.projection),
    pickLabel: pickLabel(row.edge),
    isUnder: row.edge !== null && row.edge < 0,
    edgeShareText: edgePctLabel(edgeShare(row, referenceLine)),
    edgeText: edgeLabel(row.edge),
    trust: trustLabel(row),
    sampleText: `${row.gamesInSample}g${confident ? '' : ' thin'}`,
    thin: !confident,
    injury: injuryTag(row.injuryStatus),
    depthText: row.qualityFlags.some(flag => DEPTH_FLAGS.includes(flag)) ? depthLabel(row) : null,
    flags: row.qualityFlags.filter(flag => flag !== 'historical_baseline'),
    why: signalSummary(row),
    bookText: td ? nflBookOddsEvidence(row, now)?.summary ?? 'No book price' : null,
    snapText: td ? snapShareLabel(row) : null,
  }
}

/**
 * Last games oldest to newest against the line; recentForm arrives newest first. A TD game is 0 or 1,
 * so TD gets none. History is whole-game, so a partial-segment line is not drawn against it.
 */
export function recentBars(row: Pick<NflBoardLine, 'market' | 'line' | 'recentForm' | 'segment'>): NflRecentBars {
  if (row.market === TD_MARKET || !row.recentForm.values.length) return { bars: [], linePct: null }
  const values = [...row.recentForm.values].reverse()
  const line = row.segment === 'full_game' ? row.line : null
  const scale = Math.max(line ?? 0, ...values.map(item => item.value))
  const pct = (value: number) => (scale > 0 ? Math.min(100, Math.max(0, (value / scale) * 100)) : 0)
  return {
    bars: values.map(item => ({
      value: item.value,
      opponentTeam: item.opponentTeam,
      heightPct: pct(item.value),
      vsLine: line === null ? null : item.value > line ? 'above' : item.value < line ? 'below' : 'push',
    })),
    linePct: line === null ? null : pct(line),
  }
}
