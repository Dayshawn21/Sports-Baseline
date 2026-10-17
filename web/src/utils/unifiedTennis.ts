import type { BankrollPick, BestPick, MatchBestPicks, MatchPrediction, PropLine } from '~/types/tennis'

export interface UnifiedTennisMatch {
  /** Stable React key. Prop-only groups have no matchId, so this is not the id. */
  key: string
  matchId: number | null
  prediction: MatchPrediction | null
  bestMatch: MatchBestPicks | null
  bestPicks: BestPick[]
  props: PropLine[]
  /** True when props reached this match by player-name fallback, not by matchId. */
  inferredPropLink: boolean
}

export interface UnifiedTennisFilters {
  showLeans: boolean
  upcomingOnly: boolean
  tour?: string
  date?: string
  sort?: UnifiedSort
  now?: number
}

export type UnifiedSort = 'opportunity' | 'start' | 'start_desc' | 'ev' | 'confidence' | 'items'

export const UNIFIED_SORT_OPTIONS: Array<{ value: UnifiedSort; label: string }> = [
  { value: 'opportunity', label: 'Best opportunity' },
  { value: 'start', label: 'Start time (soonest)' },
  { value: 'start_desc', label: 'Start time (latest)' },
  { value: 'ev', label: 'Highest EV' },
  { value: 'confidence', label: 'Confidence' },
  { value: 'items', label: 'Most picks' },
]

const CT_DATE_FMT = new Intl.DateTimeFormat('en-CA', {
  timeZone: 'America/Chicago',
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
})

const CONFIDENCE_RANK: Record<string, number> = {
  LOCK: 3,
  STRONG: 2,
  LEAN: 1,
}

const UPCOMING_BUFFER_MS = 3 * 60 * 60 * 1000
const MIN_BEST_BET_EV_PCT = 5

/**
 * Weights applied to a match's best, second-best and third-best EV when scoring
 * the card. Quality dominates, but depth still separates otherwise-equal cards.
 * Anything past the third item contributes nothing — a long tail of marginal
 * picks is mostly a signal that the source posted a lot of lines for that match,
 * which is data availability, not edge.
 */
const DEPTH_WEIGHTS = [1, 0.25, 0.1]

export function isVisibleConfidence(confidence: string | null | undefined, showLeans: boolean): boolean {
  if (confidence === 'LOCK' || confidence === 'STRONG') return true
  return showLeans && confidence === 'LEAN'
}

function confidenceRank(confidence: string | null | undefined): number {
  return CONFIDENCE_RANK[confidence ?? ''] ?? 0
}

function finite(value: number | null | undefined): number | null {
  return Number.isFinite(value) ? Number(value) : null
}

function edgeValue(value: number | null | undefined): number {
  return finite(value) ?? Number.NEGATIVE_INFINITY
}

/**
 * Orders the rows inside one card: confidence tier first (the visual grouping),
 * then expected value.
 *
 * Priced items sort above unpriced ones rather than being interleaved on
 * `edgePct`. EV and edgePct are different units — edgePct is a projection-vs-line
 * delta for props and a delta vs a fixed baseline for derived picks — so
 * comparing one against the other would just be noise. Unpriced items keep
 * `edgePct` as an ordering among themselves only.
 */
function sortByConfidenceAndEv<T>(
  values: T[],
  getConfidence: (value: T) => string | null | undefined,
  getEv: (value: T) => number | null | undefined,
  getEdge: (value: T) => number | null | undefined,
): T[] {
  return [...values].sort((a, b) => {
    const confidenceDiff = confidenceRank(getConfidence(b)) - confidenceRank(getConfidence(a))
    if (confidenceDiff !== 0) return confidenceDiff

    const aEv = finite(getEv(a))
    const bEv = finite(getEv(b))
    if (aEv !== null && bEv !== null) return bEv - aEv
    if (aEv !== null) return -1
    if (bEv !== null) return 1

    return edgeValue(getEdge(b)) - edgeValue(getEdge(a))
  })
}

function matchStart(match: UnifiedTennisMatch): string | null {
  return match.prediction?.startUtc ?? match.bestMatch?.startUtc ?? match.props[0]?.startTime ?? null
}

function matchTour(match: UnifiedTennisMatch): string | null {
  return match.prediction?.tour ?? match.bestMatch?.tour ?? null
}

function dateCT(value: string | null): string | null {
  if (!value) return null
  const parsed = Date.parse(value)
  return Number.isNaN(parsed) ? null : CT_DATE_FMT.format(new Date(parsed))
}

function isUpcoming(value: string | null, now: number): boolean {
  if (!value) return false
  const parsed = Date.parse(value)
  return !Number.isNaN(parsed) && parsed + UPCOMING_BUFFER_MS >= now
}

function bestPickKey(pick: BestPick): string {
  return [pick.pickType, pick.pick, pick.playerName ?? '', pick.oddsAmerican ?? '', pick.edgePct].join('|')
}

function propKey(prop: PropLine): string {
  // oddsType matters: PrizePicks demon/goblin share a line with the standard
  // pick but pay differently, so omitting it collapses them into one row.
  return [
    prop.playerName ?? '',
    prop.statType,
    prop.line ?? '',
    prop.recommendation ?? '',
    prop.source,
    prop.oddsType ?? '',
  ].join('|')
}

/** Loose name key for joining props to matches when matchId is missing. */
export function normalizeName(name: string | null | undefined): string {
  if (!name) return ''
  return name
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase()
    .replace(/[^a-z\s]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
}

function normalizedStatType(statType: string): string {
  return statType.trim().toLowerCase().replace(/\s+/g, '_')
}

function conflictsWithStraightSetsWin(prop: PropLine, pick: BestPick): boolean {
  if (pick.pickType !== 'derived' || pick.label !== 'Set Score 2-0' || !pick.playerName || !prop.playerName) {
    return false
  }
  if (normalizeName(prop.playerName) !== normalizeName(pick.playerName)) return false

  const statType = normalizedStatType(prop.statType)
  if (statType !== 'total_games_won' && statType !== 'games_won') return false
  if (prop.recommendation?.toUpperCase() !== 'OVER') return false

  const line = Number(prop.line)
  return Number.isFinite(line) && line >= 14
}

function filterCompatibleProps(bestPicks: BestPick[], props: PropLine[]): PropLine[] {
  const straightSetsPicks = bestPicks.filter(
    (pick) => pick.pickType === 'derived' && pick.label === 'Set Score 2-0',
  )
  if (straightSetsPicks.length === 0) return props
  return props.filter((prop) => !straightSetsPicks.some((pick) => conflictsWithStraightSetsWin(prop, pick)))
}

function bankrollPlayerName(pick: BankrollPick): string | null {
  if (pick.pickSide === 'p1') return pick.p1Name
  if (pick.pickSide === 'p2') return pick.p2Name
  return null
}

function bankrollPickType(): string {
  return 'bankroll'
}

function bankrollLabel(pick: BankrollPick): string {
  if (pick.betType === 'ml') return 'Moneyline'
  if (pick.betType === '2-0') return 'Set Score 2-0'
  if (pick.betType === '3-0') return 'Set Score 3-0'
  if (pick.betType === 'underdog_set') return 'Win a Set'
  if (pick.betType === 'total_games') return 'Total Games'
  return pick.betType
}

function bankrollToBestPick(pick: BankrollPick): BestPick {
  return {
    pickType: bankrollPickType(),
    label: bankrollLabel(pick),
    pick: pick.pickLabel,
    playerName: bankrollPlayerName(pick),
    edgePct: pick.edgePct,
    confidence: pick.confidence,
    reasoning: pick.reasoning,
    oddsAmerican: pick.oddsAmerican,
    evPct: pick.ev * 100,
    modelProb: pick.ourProb,
    marketProb: pick.marketProb,
    kellyFraction: pick.kellyFraction,
    dataQualityFlags: [],
    oddsSource: 'posted',
  }
}

function isPricedBestBet(pick: BestPick): boolean {
  if (pick.evPct == null || pick.evPct < MIN_BEST_BET_EV_PCT) return false
  if (pick.kellyFraction == null || pick.kellyFraction < 0) return false
  if (pick.oddsAmerican == null) return false
  if (pick.confidence === 'LOCK') return pick.evPct >= 15 && pick.kellyFraction >= 0.03
  if (pick.confidence === 'STRONG') return pick.evPct >= 10 && pick.kellyFraction >= 0.02
  return pick.confidence === 'LEAN'
}

function isVisibleBestPick(pick: BestPick, showLeans: boolean): boolean {
  if (!isVisibleConfidence(pick.confidence, showLeans)) return false
  if (pick.evPct != null && pick.evPct < MIN_BEST_BET_EV_PCT) return false
  return true
}

function isVisibleBankrollPick(pick: BestPick, showLeans: boolean): boolean {
  return isVisibleConfidence(pick.confidence, showLeans) && isPricedBestBet(pick)
}

function overlapsWithBankrollPick(existing: BestPick, bankrollPick: BestPick): boolean {
  if (existing.pickType !== 'derived') return false
  if (existing.playerName && bankrollPick.playerName && normalizeName(existing.playerName) !== normalizeName(bankrollPick.playerName)) {
    return false
  }

  if (existing.label === bankrollPick.label) return true
  return existing.label === 'Win a Set' && bankrollPick.label === 'Win a Set'
}

// Best picks and the bankroll builder both price the same moneyline. Keep the
// best-picks copy: it carries the quality flags the bankroll conversion drops.
function duplicatesMoneyline(existing: BestPick[], bankrollPick: BestPick): boolean {
  if (bankrollPick.label !== 'Moneyline' || !bankrollPick.playerName) return false
  const player = normalizeName(bankrollPick.playerName)
  return existing.some((pick) => pick.pickType === 'moneyline' && normalizeName(pick.playerName) === player)
}

function mergeBankrollPicks(existing: BestPick[], bankrollPicks: BestPick[], showLeans: boolean): BestPick[] {
  const visibleBankroll = bankrollPicks.filter(
    (pick) => isVisibleBankrollPick(pick, showLeans) && !duplicatesMoneyline(existing, pick),
  )
  if (visibleBankroll.length === 0) return existing

  const withoutOverlaps = existing.filter(
    (pick) => !visibleBankroll.some((bankrollPick) => overlapsWithBankrollPick(pick, bankrollPick)),
  )
  return dedupe([...withoutOverlaps, ...visibleBankroll], bestPickKey)
}

/**
 * Best picks to render alongside the prop rows.
 *
 * When real prop rows exist, best picks of type `prop` are suppressed — they
 * restate the same recommendation from a second endpoint. Shared by the card
 * and the header counts so the two cannot drift.
 */
export function displayedBestPicks(match: UnifiedTennisMatch): BestPick[] {
  if (match.props.length === 0) return match.bestPicks
  return match.bestPicks.filter((pick) => pick.pickType !== 'prop')
}

export function bestBetPicks(match: UnifiedTennisMatch): BestPick[] {
  return displayedBestPicks(match).filter(isPricedBestBet)
}

export function anglePicks(match: UnifiedTennisMatch): BestPick[] {
  return displayedBestPicks(match).filter((pick) => !isPricedBestBet(pick))
}

export interface PropsHealth {
  total: number
  linked: number
  scored: number
  /** True when props loaded but are structurally unusable, not merely absent. */
  degraded: boolean
  /**
   * `unlinked`   — props exist but never got a matchId, so confidence was suppressed.
   * `unsupported`— the source only carries markets the projection model can't score.
   * `none`       — healthy, or nothing loaded at all.
   */
  reason: 'unlinked' | 'unsupported' | 'none'
}

/**
 * Props can arrive in bulk and still be unusable: linking happens upstream, and
 * an unlinked prop also loses its confidence. `isError` is false in that case,
 * so without this the page reports a broken pipeline as a confident zero.
 */
export function assessPropsHealth(props: PropLine[]): PropsHealth {
  const total = props.length
  const linked = props.filter((prop) => prop.matchId != null).length
  const scored = props.filter((prop) => prop.confidence != null).length
  const unsupported = props.filter((prop) => prop.projectionStatus === 'unsupported_stat').length

  if (total === 0 || scored / total >= 0.1) {
    return { total, linked, scored, degraded: false, reason: 'none' }
  }
  return {
    total,
    linked,
    scored,
    degraded: true,
    reason: unsupported / total >= 0.9 ? 'unsupported' : 'unlinked',
  }
}

function dedupe<T>(values: T[], keyFor: (value: T) => string): T[] {
  const seen = new Set<string>()
  return values.filter((value) => {
    const key = keyFor(value)
    if (seen.has(key)) return false
    seen.add(key)
    return true
  })
}

/**
 * Every item the card actually renders, once each.
 *
 * `displayedBestPicks` drops best picks of type `prop` when real prop rows are
 * present, so the same underlying edge is not counted twice — that double count
 * used to inflate exactly the matches where both endpoints had data.
 */
function rankedItems(match: UnifiedTennisMatch): Array<{ confidence: string | null; evPct: number | null; priced: boolean }> {
  return [
    ...displayedBestPicks(match).map((pick) => ({
      confidence: pick.confidence,
      evPct: finite(pick.evPct),
      priced: isPricedBestBet(pick),
    })),
    ...match.props.map((prop) => ({
      confidence: prop.confidence,
      evPct: finite(prop.evPct),
      priced: prop.evPct != null && prop.evPct >= MIN_BEST_BET_EV_PCT,
    })),
  ]
}

/**
 * How good this match's opportunities are, as a single number: the best EV on
 * the card plus a sharply decayed contribution from the next two.
 *
 * Ranking on quality rather than on how many LOCKs a card holds — three picks
 * barely over the +15% LOCK threshold are worth less than one at +40%, and item
 * counts track how many lines the source posted more than they track edge.
 *
 * Returns null when nothing on the card is priced, so unpriced matches can be
 * ordered separately instead of being handed an invented EV.
 */
function matchOpportunityScore(match: UnifiedTennisMatch): number | null {
  const evs = rankedItems(match)
    .filter((item) => item.priced)
    .map((item) => item.evPct)
    .filter((ev): ev is number => ev !== null)
    .sort((a, b) => b - a)
  if (evs.length === 0) return null
  return evs
    .slice(0, DEPTH_WEIGHTS.length)
    .reduce((sum, ev, index) => sum + ev * DEPTH_WEIGHTS[index], 0)
}

function topConfidenceRank(match: UnifiedTennisMatch): number {
  return rankedItems(match).reduce((best, item) => Math.max(best, confidenceRank(item.confidence)), 0)
}

/** Best single priced EV on the card, or null when nothing on it is priced. */
function topEv(match: UnifiedTennisMatch): number | null {
  return rankedItems(match).reduce<number | null>((best, item) => {
    if (!item.priced || item.evPct === null) return best
    return best === null || item.evPct > best ? item.evPct : best
  }, null)
}

function itemCount(match: UnifiedTennisMatch): number {
  return rankedItems(match).length
}

function startMs(match: UnifiedTennisMatch): number | null {
  const start = matchStart(match)
  if (!start) return null
  const parsed = Date.parse(start)
  return Number.isNaN(parsed) ? null : parsed
}

/** Unknown values sort last in both directions rather than leading a descending list. */
function compareNullable(a: number | null, b: number | null, direction: 1 | -1): number {
  if (a === null && b === null) return 0
  if (a === null) return 1
  if (b === null) return -1
  return (a - b) * direction
}

/**
 * Order by opportunity quality, not by how many items a card happens to hold.
 * Priced matches come first, ranked by their EV score; unpriced ones fall back
 * to confidence tier. Item counts are deliberately not part of this - they made
 * the page order swing on the "show leans" toggle and on how many lines the prop
 * source posted for a given match. The explicit "Most picks" sort exists for
 * when the user actually wants that.
 */
function compareByOpportunity(
  a: UnifiedTennisMatch,
  b: UnifiedTennisMatch,
  scores: Map<string, number | null>,
): number {
  const aScore = scores.get(a.key) ?? null
  const bScore = scores.get(b.key) ?? null
  if (aScore !== null && bScore !== null) {
    if (aScore !== bScore) return bScore - aScore
  } else if (aScore !== null) {
    return -1
  } else if (bScore !== null) {
    return 1
  }

  const confidenceDiff = topConfidenceRank(b) - topConfidenceRank(a)
  if (confidenceDiff !== 0) return confidenceDiff

  return compareNullable(startMs(a), startMs(b), 1)
}

/**
 * Every sort falls back to opportunity quality once its own key ties, so a sort
 * on a coarse key (confidence tier, pick count) still puts the better card first
 * inside each group.
 */
export function sortUnifiedMatches(
  matches: UnifiedTennisMatch[],
  sort: UnifiedSort = 'opportunity',
): UnifiedTennisMatch[] {
  const scores = new Map(matches.map((match) => [match.key, matchOpportunityScore(match)]))
  const byOpportunity = (a: UnifiedTennisMatch, b: UnifiedTennisMatch) => compareByOpportunity(a, b, scores)

  const comparators: Record<UnifiedSort, (a: UnifiedTennisMatch, b: UnifiedTennisMatch) => number> = {
    opportunity: byOpportunity,
    start: (a, b) => compareNullable(startMs(a), startMs(b), 1) || byOpportunity(a, b),
    start_desc: (a, b) => compareNullable(startMs(a), startMs(b), -1) || byOpportunity(a, b),
    ev: (a, b) => compareNullable(topEv(a), topEv(b), -1) || byOpportunity(a, b),
    confidence: (a, b) => topConfidenceRank(b) - topConfidenceRank(a) || byOpportunity(a, b),
    items: (a, b) => itemCount(b) - itemCount(a) || byOpportunity(a, b),
  }

  return [...matches].sort(comparators[sort] ?? byOpportunity)
}

export function composeUnifiedMatches(
  predictions: MatchPrediction[],
  bestMatches: MatchBestPicks[],
  props: PropLine[],
  filters: UnifiedTennisFilters,
  bankrollPicks: BankrollPick[] = [],
): UnifiedTennisMatch[] {
  const byMatchId = new Map<number, UnifiedTennisMatch>()
  const getMatch = (matchId: number) => {
    let match = byMatchId.get(matchId)
    if (!match) {
      match = {
        key: `m-${matchId}`,
        matchId,
        prediction: null,
        bestMatch: null,
        bestPicks: [],
        props: [],
        inferredPropLink: false,
      }
      byMatchId.set(matchId, match)
    }
    return match
  }

  predictions.forEach((prediction) => {
    getMatch(prediction.matchId).prediction = prediction
  })
  bestMatches.forEach((bestMatch) => {
    const match = getMatch(bestMatch.matchId)
    match.bestMatch = bestMatch
    match.bestPicks.push(...bestMatch.picks)
  })
  bankrollPicks.forEach((bankrollPick) => {
    getMatch(bankrollPick.matchId).bestPicks.push(bankrollToBestPick(bankrollPick))
  })

  // Props carry a matchId only when upstream linked them. Anything unlinked is
  // recovered by player name on the same CT date, and whatever still has no home
  // becomes a prop-only card rather than being silently dropped.
  const nameIndex = new Map<string, UnifiedTennisMatch>()
  byMatchId.forEach((match) => {
    const source = match.prediction ?? match.bestMatch
    if (!source) return
    const day = dateCT(source.startUtc)
    for (const name of [source.p1Name, source.p2Name]) {
      const key = normalizeName(name)
      if (key) nameIndex.set(`${key}|${day ?? ''}`, match)
    }
  })

  const orphanProps: PropLine[] = []
  props.forEach((prop) => {
    if (prop.matchId != null) {
      getMatch(prop.matchId).props.push(prop)
      return
    }
    const key = `${normalizeName(prop.playerName)}|${dateCT(prop.startTime) ?? ''}`
    const viaName = normalizeName(prop.playerName) ? nameIndex.get(key) : undefined
    if (viaName) {
      viaName.props.push(prop)
      viaName.inferredPropLink = true
    } else {
      orphanProps.push(prop)
    }
  })

  const byPlayer = new Map<string, UnifiedTennisMatch>()
  orphanProps.forEach((prop) => {
    const name = normalizeName(prop.playerName)
    if (!name) return
    const key = `p-${name}|${dateCT(prop.startTime) ?? ''}`
    let group = byPlayer.get(key)
    if (!group) {
      group = {
        key,
        matchId: null,
        prediction: null,
        bestMatch: null,
        bestPicks: [],
        props: [],
        inferredPropLink: true,
      }
      byPlayer.set(key, group)
    }
    group.props.push(prop)
  })

  const now = filters.now ?? Date.now()
  const all = [...byMatchId.values(), ...byPlayer.values()]
  const visible = all.flatMap((match) => {
    const sourceBestPicks = match.bestPicks.filter((pick) => pick.pickType !== 'bankroll')
    const bankrollBestPicks = match.bestPicks.filter((pick) => pick.pickType === 'bankroll')
    const bestPicks = sortByConfidenceAndEv(
      mergeBankrollPicks(
        dedupe(sourceBestPicks.filter((pick) => isVisibleBestPick(pick, filters.showLeans)), bestPickKey),
        dedupe(bankrollBestPicks, bestPickKey),
        filters.showLeans,
      ),
      (pick) => pick.confidence,
      (pick) => pick.evPct,
      (pick) => pick.edgePct,
    )
    const visibleProps = sortByConfidenceAndEv(
      dedupe(match.props.filter((prop) => (
        isVisibleConfidence(prop.confidence, filters.showLeans)
          && (prop.evPct == null || prop.evPct >= MIN_BEST_BET_EV_PCT)
      )), propKey),
      (prop) => prop.confidence,
      // Rank on expected value. edgePct is a projection-vs-line delta that
      // ignores payout, so it ranked cheap near-certain goblins at the top.
      (prop) => prop.evPct,
      (prop) => prop.edgePct,
    )

    const candidateBestPicks = visibleProps.length > 0
      ? bestPicks.filter((pick) => pick.pickType !== 'prop')
      : bestPicks
    const compatibleProps = filterCompatibleProps(candidateBestPicks, visibleProps)
    const candidate = { ...match, bestPicks: candidateBestPicks, props: compatibleProps }
    if (candidateBestPicks.length === 0 && compatibleProps.length === 0) return []
    if (filters.tour && matchTour(candidate) !== filters.tour) return []
    if (filters.date && dateCT(matchStart(candidate)) !== filters.date) return []
    if (filters.upcomingOnly && !isUpcoming(matchStart(candidate), now)) return []
    return [candidate]
  })

  return sortUnifiedMatches(visible, filters.sort)
}

export function unifiedMatchToPrediction(match: UnifiedTennisMatch): MatchPrediction | null {
  if (match.prediction) return match.prediction
  if (!match.bestMatch) return null
  const best = match.bestMatch
  return {
    matchId: best.matchId,
    startUtc: best.startUtc,
    p1Name: best.p1Name,
    p2Name: best.p2Name,
    tour: best.tour,
    tourLabel: best.tourLabel,
    surface: best.surface,
    tournament: best.tournament,
    round: best.round,
    p1WinProb: best.p1WinProb,
    p2WinProb: best.p2WinProb,
    p1EloProb: null,
    p1MlProb: null,
    p1MarketProb: null,
    ensembleWeights: {},
    qualityFlags: [],
    p1OddsAmerican: best.p1OddsAmerican,
    p2OddsAmerican: best.p2OddsAmerican,
    h2hP1Wins: best.h2hP1Wins,
    h2hP2Wins: best.h2hP2Wins,
  }
}
