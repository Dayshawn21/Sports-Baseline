import type { BestPick, PropLine } from '~/types/tennis'
import type { UnifiedSort, UnifiedTennisMatch } from '~/utils/unifiedTennis'
import { anglePicks, bestBetPicks, unifiedMatchToPrediction } from '~/utils/unifiedTennis'
import { getDisplayFlags } from '~/components/tennis/qualityFlags'
import { fmtStartCT, fmtTournament } from '~/utils/format'
import { fmtAmerican } from '~/utils/odds'

type Pair = [number, number]

export function matchAnalysisPath(match: UnifiedTennisMatch): string | null {
  return match.matchId == null ? null : `/tennis/match/${match.matchId}`
}

export interface SlateRow {
  key: string
  match: UnifiedTennisMatch
  startUtc: string | null
  tournament: string | null
  tour: string | null
  /** WTA 125 draws arrive as tour CHALLENGER; this carries the real label. */
  tourLabel: string | null
  /** Prop-only rows may know a single player. */
  players: [string, string | null]
  elo: Pair | null
  ml: Pair | null
  market: Pair | null
  model: Pair | null
  odds: [number | null, number | null]
  primaryPick: BestPick | null
  primaryIsBestBet: boolean
  /** First prop in board order, the fallback the slate shows when a match has no pick. */
  primaryProp: PropLine | null
  propCount: number
  flags: string[]
}

export interface TournamentGroup {
  /** null for the single header-less group of a ranked (ungrouped) table. */
  tournament: string | null
  rows: SlateRow[]
}

export interface FeaturedPick {
  match: UnifiedTennisMatch
  pick: BestPick
}

export const OTHER_TOURNAMENT = 'Other'

function pair(p1: number | null | undefined, p2?: number | null): Pair | null {
  if (p1 == null) return null
  return [p1, p2 ?? 1 - p1]
}

// The card's first line in board order, never the highest-EV one: only adopted props are ranked (48f, 48g).
function firstProp(match: UnifiedTennisMatch): PropLine | null {
  return match.props[0] ?? null
}

function propPlayers(match: UnifiedTennisMatch): [string, string | null] {
  const names = [...new Set(match.props.map((prop) => prop.playerName).filter((name): name is string => !!name))]
  return [names[0] ?? 'Unlinked player props', names[1] ?? null]
}

export function slateRow(match: UnifiedTennisMatch): SlateRow {
  const prediction = unifiedMatchToPrediction(match)
  const bestBet = bestBetPicks(match)[0] ?? null
  return {
    key: match.key,
    match,
    startUtc: prediction?.startUtc ?? match.props[0]?.startTime ?? null,
    tournament: prediction?.tournament ?? null,
    tour: prediction?.tour ?? null,
    tourLabel: prediction?.tourLabel ?? null,
    players: prediction ? [prediction.p1Name, prediction.p2Name] : propPlayers(match),
    elo: pair(prediction?.p1EloProb),
    ml: pair(prediction?.p1MlProb),
    market: pair(prediction?.p1MarketProb),
    model: pair(prediction?.p1WinProb, prediction?.p2WinProb),
    odds: [prediction?.p1OddsAmerican ?? null, prediction?.p2OddsAmerican ?? null],
    primaryPick: bestBet ?? anglePicks(match)[0] ?? null,
    primaryIsBestBet: bestBet != null,
    primaryProp: firstProp(match),
    propCount: match.props.length,
    flags: prediction ? getDisplayFlags(prediction.qualityFlags) : [],
  }
}

export function slateRows(matches: UnifiedTennisMatch[]): SlateRow[] {
  return matches.map(slateRow)
}

/** Groups keep the order of their first row, so the top-ranked match's tournament leads. */
export function groupByTournament(rows: SlateRow[]): TournamentGroup[] {
  const groups = new Map<string, SlateRow[]>()
  for (const row of rows) {
    const name = row.tournament ?? OTHER_TOURNAMENT
    const group = groups.get(name)
    if (group) group.push(row)
    else groups.set(name, [row])
  }
  return [...groups].map(([tournament, groupRows]) => ({ tournament, rows: groupRows }))
}

/** EV as shown across the slate: signed, one decimal, a dash when unpriced. */
export function fmtEv(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) return '—'
  return `${value >= 0 ? '+' : ''}${value.toFixed(1)}%`
}

export type TourTab = 'all' | 'ATP' | 'WTA' | 'CHALLENGER' | 'WTA 125'

export const TOUR_TABS: TourTab[] = ['all', 'ATP', 'WTA', 'CHALLENGER', 'WTA 125']

function isWta125(row: SlateRow): boolean {
  return (row.tourLabel ?? '').toUpperCase().includes('WTA 125')
}

/** The slate's tour tabs. WTA 125 is its own tab even though the feed files it under CHALLENGER. */
export function filterByTourTab(rows: SlateRow[], tab: TourTab): SlateRow[] {
  if (tab === 'all') return rows
  if (tab === 'WTA 125') return rows.filter(isWta125)
  return rows.filter((row) => row.tour === tab && !isWta125(row))
}

export type TourTone = 'atp' | 'wta' | 'challenger'

/** Tour color for a match. WTA 125 arrives as tour CHALLENGER, so the label wins. */
export function tourTone(tour: string | null | undefined, tourLabel?: string | null): TourTone | null {
  const label = (tourLabel ?? '').toUpperCase()
  if (label.includes('WTA')) return 'wta'
  const code = (tour ?? '').toUpperCase()
  if (code === 'CHALLENGER' || label.includes('CHALLENGER')) return 'challenger'
  if (code === 'ATP') return 'atp'
  if (code === 'WTA') return 'wta'
  return null
}

/**
 * Tournament headers only make sense in time order. Under a ranking sort they
 * would pull a tournament's weaker matches above the next tournament's best one.
 */
export function isGroupedSort(sort: UnifiedSort): boolean {
  return sort === 'start' || sort === 'start_desc'
}

export function tableGroups(rows: SlateRow[], grouped: boolean): TournamentGroup[] {
  if (!grouped) return rows.length ? [{ tournament: null, rows }] : []
  return groupByTournament(rows)
}

/** One box of the tennis digest; display strings only. The EV is a priced best bet's, so the box shows it green. */
export interface TennisDigestItem {
  matchKey: string
  analysisPath: string | null
  pick: string
  what: string
  when: string
  odds: string
  ev: string
  tier: string
  tourLabel: string | null
  tone: TourTone | null
}

export function tennisDigest(featured: FeaturedPick[], now: number = Date.now()): TennisDigestItem[] {
  return featured.map(({ match, pick }) => {
    const prediction = unifiedMatchToPrediction(match)
    // fmtStartCT answers '' rather than null for a missing or unreadable time.
    const start = fmtStartCT(prediction?.startUtc, now) || 'Time TBA'
    return {
      matchKey: match.key,
      analysisPath: matchAnalysisPath(match),
      pick: pick.pick,
      what: prediction ? `${pick.label} · ${prediction.p1Name} vs ${prediction.p2Name}` : pick.label,
      when: `${fmtTournament(prediction?.tournament ?? null)} · ${start}`,
      odds: fmtAmerican(pick.oddsAmerican),
      ev: fmtEv(pick.evPct),
      tier: pick.confidence,
      tourLabel: prediction?.tourLabel ?? prediction?.tour ?? null,
      tone: tourTone(prediction?.tour, prediction?.tourLabel),
    }
  })
}

/** The tab to show so the row with `key` is visible: the current one when it already is, else All. */
export function revealTab(rows: SlateRow[], key: string, tab: TourTab): TourTab {
  if (!rows.some((row) => row.key === key)) return tab
  return filterByTourTab(rows, tab).some((row) => row.key === key) ? tab : 'all'
}

export function featuredPicks(matches: UnifiedTennisMatch[], limit: number): FeaturedPick[] {
  const featured: FeaturedPick[] = []
  for (const match of matches) {
    const pick = bestBetPicks(match)[0]
    if (pick) featured.push({ match, pick })
    if (featured.length === limit) break
  }
  return featured
}
