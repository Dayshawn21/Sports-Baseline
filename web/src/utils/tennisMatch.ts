import type { MatchDetail, MatchPlayerDetail, PropLine } from '~/types/tennis'
import { fmtSurface, fmtTournament } from '~/utils/format'

export type Side = 'p1' | 'p2'

export interface SideView {
  side: Side
  name: string
  modelProb: number | null
  marketProb: number | null
  odds: number | null
}

export function parseMatchId(raw: string | undefined): number | null {
  if (!raw || !/^\d+$/.test(raw)) return null
  const id = Number(raw)
  return Number.isSafeInteger(id) && id > 0 ? id : null
}

/** The side the hero leads with: the moneyline play when there is one, else the model's favorite. */
export function heroSide(detail: MatchDetail): Side {
  const { prediction, mlPick } = detail
  if (mlPick?.playerName && prediction && mlPick.playerName === prediction.p2Name) return 'p2'
  if (mlPick?.playerName && prediction && mlPick.playerName === prediction.p1Name) return 'p1'
  const p1 = prediction?.p1WinProb
  const p2 = prediction?.p2WinProb
  return p1 != null && p2 != null && p2 > p1 ? 'p2' : 'p1'
}

function complement(p: number | null | undefined): number | null {
  return p == null ? null : 1 - p
}

export function sideView(detail: MatchDetail, side: Side): SideView {
  const p = detail.prediction
  const isP1 = side === 'p1'
  return {
    side,
    name: detail[side].name,
    modelProb: (isP1 ? p?.p1WinProb : p?.p2WinProb) ?? null,
    marketProb: isP1 ? p?.p1MarketProb ?? null : complement(p?.p1MarketProb),
    odds: (isP1 ? p?.p1OddsAmerican : p?.p2OddsAmerican) ?? null,
  }
}

/** e.g. "Tokyo · R16 · Hard, indoor · Bo3" */
export function matchContext(detail: MatchDetail): string {
  const surface = detail.surface
    ? `${fmtSurface(detail.surface)}${detail.indoor ? ', indoor' : ''}`
    : null
  return [
    detail.tournament ? fmtTournament(detail.tournament, 40) : null,
    detail.round,
    surface,
    `Bo${detail.bestOf}`,
  ].filter(Boolean).join(' · ')
}

/** e.g. "#19 · R · ELO hard 1968"; parts that are unknown are left out. */
export function playerMeta(player: MatchPlayerDetail, surface: string | null): string {
  const elo = player.eloSurface != null && surface
    ? `ELO ${surface.toLowerCase()} ${Math.round(player.eloSurface)}`
    : player.elo != null ? `ELO ${Math.round(player.elo)}` : null
  return [player.rank != null ? `#${player.rank}` : null, player.hand, elo].filter(Boolean).join(' · ')
}

/** Two- or three-letter badge: the country code when known, else initials. */
export function playerBadge(player: Pick<MatchPlayerDetail, 'name' | 'country'>): string {
  if (player.country) return player.country.slice(0, 3).toUpperCase()
  return player.name.split(/\s+/).filter(Boolean).map((part) => part[0]).join('').slice(0, 2).toUpperCase()
}

export function isFinished(detail: MatchDetail): boolean {
  return detail.status !== 'scheduled' && detail.status !== 'live'
}

function propRank(prop: PropLine): number {
  return !prop.oddsType || prop.oddsType === 'standard' ? 0 : 1
}

/** A match's prop lines, standard lines first, otherwise in feed order: tennis props carry no tier (48f). */
export function matchProps(props: PropLine[], matchId: number): PropLine[] {
  return props
    .filter((p) => p.matchId === matchId)
    .map((p, i) => ({ p, i }))
    .sort((a, b) => propRank(a.p) - propRank(b.p) || a.i - b.i)
    .map(({ p }) => p)
}

/** "2/5" break points won, or a dash when the box score is missing or had no chances. */
export function fmtBreakPoints(converted: number | null, created: number | null): string {
  if (converted == null || created == null || created === 0) return '—'
  return `${converted}/${created}`
}

const SHORT_DATE = new Intl.DateTimeFormat('en-US', { month: 'short', day: 'numeric', timeZone: 'UTC' })

/** A date-only "YYYY-MM-DD" as "Sep 25"; read in UTC so it never slips to the day before. */
export function fmtMatchDate(isoDate: string): string {
  const ts = Date.parse(`${isoDate}T00:00:00Z`)
  return Number.isNaN(ts) ? isoDate : SHORT_DATE.format(new Date(ts))
}

const DATE_WITH_YEAR = new Intl.DateTimeFormat('en-US', { month: 'short', day: 'numeric', year: 'numeric', timeZone: 'UTC' })

/** A date-only "YYYY-MM-DD" as "Feb 18, 2026", for lists that span years. */
export function fmtMatchDateYear(isoDate: string): string {
  const ts = Date.parse(`${isoDate}T00:00:00Z`)
  return Number.isNaN(ts) ? isoDate : DATE_WITH_YEAR.format(new Date(ts))
}

/**
 * Says when the listed meetings fall short of the head-to-head count. The count is
 * the provider's all-time record; stored matches only start in 2023.
 */
export function meetingsNote(listed: number, counted: number): string | null {
  if (listed >= counted) return null
  return `${listed} of ${counted} meetings shown · stored since 2023`
}

export interface ComponentRow {
  key: 'elo' | 'ml' | 'market' | 'ensemble'
  label: string
  prob: number | null
  weight: number | null
  /** Why prob is missing, shown in its place; never rendered as 0%. */
  missingNote: string | null
}

function forSide(p1Prob: number | null | undefined, side: Side): number | null {
  if (p1Prob == null) return null
  return side === 'p1' ? p1Prob : 1 - p1Prob
}

/**
 * ensemble-v3 (26d) stores log-odds coefficients, not shares that sum to 1. A live
 * prediction carries no stored version, but with a market price it is always v3.
 */
export function weightColumnLabel(detail: MatchDetail): 'Coef' | 'Weight' {
  const major = Number(/^ensemble-v(\d+)/.exec(detail.modelVersion ?? '')?.[1] ?? 0)
  if (major >= 3) return 'Coef'
  const liveWithMarket = detail.predictionSource === 'live' && detail.prediction?.p1MarketProb != null
  return liveWithMarket ? 'Coef' : 'Weight'
}

/** ELO, ML, market and the blend, each as the given side's win probability. */
export function componentRows(detail: MatchDetail, side: Side): ComponentRow[] {
  const p = detail.prediction
  const weights = p?.ensembleWeights ?? {}
  const mlUntrained = p?.qualityFlags.includes('ml_not_trained_for_tour') ?? false
  const eloLabel = detail.surface ? `ELO (${detail.surface.toLowerCase()})` : 'ELO'
  const row = (key: ComponentRow['key'], label: string, prob: number | null, untrainedNote?: string): ComponentRow => ({
    key,
    label,
    prob,
    weight: key === 'ensemble' ? null : weights[key] ?? null,
    missingNote: prob != null ? null : untrainedNote ?? 'no data',
  })
  return [
    row('elo', eloLabel, forSide(p?.p1EloProb, side)),
    row('ml', 'LightGBM', forSide(p?.p1MlProb, side), mlUntrained ? 'not trained for this tour' : undefined),
    row('market', 'Market', forSide(p?.p1MarketProb, side)),
    row('ensemble', 'Ensemble', side === 'p1' ? p?.p1WinProb ?? null : p?.p2WinProb ?? null),
  ]
}
