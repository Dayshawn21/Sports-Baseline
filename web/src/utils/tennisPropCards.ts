import type { RecentMatchResult } from '~/types/tennis'
import type { TennisBoardLine } from '~/utils/tennisPropBoard'
import { isMoneyline, isWinASet, lineNumber, marketLabel, payoutTier, sourceLabel, trustLabel } from '~/utils/tennisPropBoard'

export interface TennisPropCardModel {
  key: string
  playerName: string
  meta: string
  startText: string
  tour: string | null
  payoutTier: 'standard' | 'goblin' | 'demon' | null
  flags: string[]
  isUnder: boolean
  pickLabel: string
  valueLabel: 'Line' | 'Odds' | 'Market'
  valueText: string
  unit: string | null
  projectionText: string
  /** Signed projection minus line, or null where the row has no line to compare. */
  gapText: string | null
  /** P(over), push excluded, on a PrizePicks line; the model's probability on a moneyline or Win a Set row. */
  hitPct: number | null
  breakEvenPct: number | null
  breakEvenLabel: string | null
  evText: string
  evTone: 'positive' | 'negative' | null
  opponentText: string | null
  trust: string
  source: string
  sampleText: string
}

const START_FORMAT = new Intl.DateTimeFormat('en-US', { timeZone: 'America/Chicago', month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit', hour12: true })

export function startLabel(value: string | null): string {
  const time = value ? Date.parse(value) : Number.NaN
  return Number.isNaN(time) ? 'Time unavailable' : `${START_FORMAT.format(time)} CT`
}

function clampPct(value: number | null | undefined): number | null {
  return value == null ? null : Math.min(100, Math.max(0, value))
}

function signed(value: number, digits: number): string {
  return `${value >= 0 ? '+' : ''}${value.toFixed(digits)}`
}

function evTone(evPct: number | null | undefined): TennisPropCardModel['evTone'] {
  if (evPct == null || evPct === 0) return null
  return evPct > 0 ? 'positive' : 'negative'
}

function valueText(row: TennisBoardLine): string {
  const line = lineNumber(row)
  if (line == null) return isWinASet(row) ? 'Unpriced' : '--'
  return isMoneyline(row) ? signed(line, 0) : line.toFixed(1)
}

function breakEvenLabel(row: TennisBoardLine, breakEven: number | null): string | null {
  if (breakEven == null) return null
  if (isMoneyline(row)) return `Market ${breakEven.toFixed(1)}%`
  const tier = payoutTier(row)
  return `Break-even ${breakEven.toFixed(1)}%${tier ? ` · ${tier}` : ''}`
}

/** P(over) with pushes excluded, the rate a payout's break-even is measured against. */
export function decisionOverPct(row: Pick<TennisBoardLine, 'pOver' | 'pUnder'>): number | null {
  if (row.pOver == null || row.pUnder == null || row.pOver + row.pUnder <= 0) return null
  return clampPct(row.pOver / (row.pOver + row.pUnder) * 100)
}

function gapText(row: TennisBoardLine, priced: boolean): string | null {
  const line = lineNumber(row)
  if (priced || line == null || row.statAvg == null) return null
  return signed(row.statAvg - line, 1)
}

// Gray and unranked (48f): a PrizePicks line names which sides are playable, never a side to take.
function prizePicksSideLabel(tier: TennisPropCardModel['payoutTier']): string {
  return tier === 'goblin' || tier === 'demon' ? 'Over only' : 'Over / under'
}

/** What one prop card shows, in the same strings the board table showed. */
export function propCard(row: TennisBoardLine): TennisPropCardModel {
  const priced = isMoneyline(row) || isWinASet(row)
  const tier = payoutTier(row)
  const direction = row.recommendation?.toUpperCase() ?? '--'
  const breakEven = clampPct(row.breakEvenPct)
  const matchFinished = !row.matchup && row.dataQualityFlags?.some(flag => flag === 'match_finished' || flag === 'match_link_invalid')
  const matchMeta = matchFinished ? 'Match finished' : row.matchup ?? [row.tour, row.surface].filter(Boolean).join(' · ')
  return {
    key: `${row.source}-${row.id}`,
    playerName: row.playerName ?? 'Unknown player',
    meta: [matchMeta, row.tournament].filter(Boolean).join(' · '),
    startText: startLabel(row.startTime),
    tour: row.tour,
    payoutTier: tier,
    flags: row.dataQualityFlags ?? [],
    isUnder: tier == null && row.recommendation === 'UNDER',
    pickLabel: isWinASet(row) ? row.confidence ?? 'MODEL' : tier != null ? prizePicksSideLabel(tier) : direction,
    valueLabel: isMoneyline(row) ? 'Odds' : isWinASet(row) ? 'Market' : 'Line',
    valueText: valueText(row),
    unit: priced ? null : marketLabel(row.statType).toLowerCase(),
    projectionText: row.statAvg == null ? '--' : priced ? `${row.statAvg.toFixed(1)}%` : row.statAvg.toFixed(1),
    gapText: gapText(row, priced),
    hitPct: tier != null ? decisionOverPct(row) : row.hitProbability == null ? null : clampPct(row.hitProbability * 100),
    breakEvenPct: breakEven,
    breakEvenLabel: breakEvenLabel(row, breakEven),
    evText: row.evPct == null ? '--' : `${signed(row.evPct, 1)}%`,
    evTone: tier != null ? null : evTone(row.evPct),
    opponentText: row.opponentStatAvg == null ? null : `Opp allows ${row.opponentStatAvg.toFixed(1)}`,
    trust: trustLabel(row),
    source: sourceLabel(row.source),
    sampleText: row.matchesCount == null ? '--' : `n=${row.matchesCount}`,
  }
}

export interface RecentStatBar {
  matchDate: string
  opponentName: string
  value: number | null
  vsLine: 'above' | 'below' | 'push' | null
}

type RecentStat = (match: RecentMatchResult) => number | null

type SetScore = [number, number]

const sum = (values: number[]) => values.reduce((total, value) => total + value, 0)
const setsWon = (sets: SetScore[]) => sets.filter(([mine, theirs]) => mine > theirs).length

function finishedSet([mine, theirs]: SetScore): boolean {
  const high = Math.max(mine, theirs)
  const low = Math.min(mine, theirs)
  return (high === 6 && low <= 4) || (high === 7 && (low === 5 || low === 6))
}

/**
 * The player's games per set from the player-oriented score, or null unless the
 * match was played out. Retirements are stored as an unfinished set ("3-6 3-5"),
 * the rule of is_completed_score in app/core/tennis_grading.py.
 */
export function playerSets(match: RecentMatchResult): SetScore[] | null {
  const cleaned = (match.score ?? '').replace(/\([^)]*\)/g, ' ')
  if (/[a-z]/i.test(cleaned)) return null
  const sets = [...cleaned.matchAll(/(\d+)-(\d+)/g)].map(([, mine, theirs]): SetScore => [Number(mine), Number(theirs)])
  if (!sets.length || !sets.every(finishedSet)) return null
  const won = setsWon(sets)
  const [lastMine, lastTheirs] = sets[sets.length - 1]
  const winnerClinched = match.result === 'W' ? won > sets.length - won && lastMine > lastTheirs : won < sets.length - won && lastMine < lastTheirs
  return winnerClinched ? sets : null
}

function fromSets(read: (sets: SetScore[]) => number): RecentStat {
  return match => {
    const sets = playerSets(match)
    return sets ? read(sets) : null
  }
}

/** PrizePicks tennis fantasy: 10 for playing, +/-1 per game, +/-3 per set, +0.5 per ace, -0.5 per double fault. */
export function fantasyScore(match: RecentMatchResult): number | null {
  const sets = playerSets(match)
  if (!sets || match.aces == null || match.doubleFaults == null) return null
  const won = setsWon(sets)
  return 10 + sum(sets.map(([mine, theirs]) => mine - theirs)) + 3 * (2 * won - sets.length) + 0.5 * match.aces - 0.5 * match.doubleFaults
}

// A 7-6 set counts as 13 games, as PrizePicks settles it (app/core/prop_settlement.py).
const RECENT_STATS: Record<string, RecentStat> = {
  aces: match => match.aces,
  double_faults: match => match.doubleFaults,
  dfs: match => match.doubleFaults,
  break_points: match => match.breakPointsConverted,
  break_points_converted: match => match.breakPointsConverted,
  break_points_won: match => match.breakPointsConverted,
  total_games: fromSets(sets => sum(sets.map(([mine, theirs]) => mine + theirs))),
  total_games_won: fromSets(sets => sum(sets.map(([mine]) => mine))),
  total_sets: fromSets(sets => sets.length),
  total_tie_breaks: fromSets(sets => sets.filter(([mine, theirs]) => Math.max(mine, theirs) === 7 && Math.min(mine, theirs) === 6).length),
  '1st_set_total_games': fromSets(([[mine, theirs]]) => mine + theirs),
  '1st_set_total_games_won': fromSets(([[mine]]) => mine),
  fantasy_score: fantasyScore,
}

/** Recent values against the line, oldest first; null for markets the score and box score cannot settle. */
export function recentStatBars(matches: RecentMatchResult[], statType: string, line: number): RecentStatBar[] | null {
  const stat = RECENT_STATS[statType.trim().toLowerCase().replaceAll(' ', '_')]
  if (!stat) return null
  return [...matches]
    .sort((left, right) => left.matchDate.localeCompare(right.matchDate))
    .map(match => {
      const value = stat(match)
      const vsLine = value == null ? null : value > line ? 'above' : value < line ? 'below' : 'push'
      return { matchDate: match.matchDate, opponentName: match.opponentName, value, vsLine }
    })
}
