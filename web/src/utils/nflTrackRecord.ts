import type { NflModelClv, NflModelRanking, NflRankingModelVersion } from '~/types/nfl'
import type { PropRankingRecord, PropRankingSlice } from '~/types/propRanking'
import { sampleProgress } from '~/utils/trackRecord'

type SliceVerdict = PropRankingSlice['verdict']
type ClvVerdict = NflModelClv['markets'][number]['verdict']

export const NFL_V4_RANKING_MODEL: NflRankingModelVersion = 'opponent-dvp-tg-blend-usage-snap-v4'
export const NFL_TARGETS_RANKING_MODEL: NflRankingModelVersion = 'nfl-targets-v1'

export function rankingParams(season: number, modelVersion: NflRankingModelVersion = NFL_V4_RANKING_MODEL) {
  return modelVersion === NFL_V4_RANKING_MODEL ? { season } : { season, model_version: modelVersion }
}

export function rankingQueryKey(season: number | null, modelVersion: NflRankingModelVersion = NFL_V4_RANKING_MODEL) {
  return ['nfl', 'model', 'ranking', { season, modelVersion }] as const
}

export function rankingPresentation(data: PropRankingRecord<string | null>, referenceOnly = false) {
  return {
    slices: referenceOnly ? data.slices.filter((slice) => slice.oddsType === 'standard') : data.slices,
    probabilityVersion: data.overProbabilityVersion ?? 'Not served',
    empty: data.frozenRows === 0,
  }
}

export function rankingSliceStatus(slice: PropRankingSlice, referenceOnly = false) {
  return {
    label: referenceOnly ? 'Not accruing' : verdictLabel(slice.verdict),
    signal: referenceOnly ? 'neutral' as const : slice.signal,
    noPicks: referenceOnly ? 'No probability picks' : 'No picks yet',
  }
}

const ODDS_TYPE_LABELS: Record<PropRankingSlice['oddsType'], string> = {
  standard: 'Standard', goblin: 'Goblin', demon: 'Demon',
}

export function sliceLabel(oddsType: PropRankingSlice['oddsType'], side: PropRankingSlice['side']): string {
  return `${ODDS_TYPE_LABELS[oddsType]} ${side}`
}

const VERDICT_LABELS: Record<SliceVerdict | ClvVerdict, string> = {
  insufficient: 'Accruing', accruing: 'Accruing', adopt: 'Adopt', pass: 'Pass', reject: 'Reject',
}

/** The 27i rule says "insufficient" and the 28 rule "accruing"; both mean the sample is still filling. */
export function verdictLabel(verdict: SliceVerdict | ClvVerdict): string {
  return VERDICT_LABELS[verdict]
}

/**
 * How full a slice's verdict sample is. It needs both enough picks and enough
 * weeks, so the bar shows whichever is further behind: 200 picks in one week
 * is a quarter done, not finished.
 */
export function sliceProgress(n: number, weeks: number, minPicks: number, minWeeks: number): number {
  return Math.min(sampleProgress(n, minPicks), sampleProgress(weeks, minWeeks))
}

export interface SummaryCounts {
  slicesAdopted: string
  gameLineVerdicts: string
  gameLinePasses: string
  lastSettledWeek: string
}

const PENDING = '—'

/** The summary strip; each figure waits for its own section, so one slow endpoint never blanks the rest. */
export function summaryCounts(ranking: NflModelRanking | undefined, clv: NflModelClv | undefined): SummaryCounts {
  if (ranking?.modelVersion === NFL_TARGETS_RANKING_MODEL) ranking = undefined
  const adopted = ranking?.slices.filter((s) => s.verdict === 'adopt').length
  const decided = clv?.markets.filter((m) => m.verdict !== 'accruing')
  const passed = decided?.filter((m) => m.verdict === 'pass').length
  let lastSettledWeek = PENDING
  if (ranking) lastSettledWeek = ranking.lastSettledWeek === null ? 'None yet' : `W${ranking.lastSettledWeek}`
  return {
    slicesAdopted: ranking ? `${adopted} of ${ranking.slices.length}` : PENDING,
    gameLineVerdicts: clv && decided ? `${decided.length} of ${clv.markets.length}` : PENDING,
    gameLinePasses: passed === undefined ? '' : `${passed} passed`,
    lastSettledWeek,
  }
}

/** Points with an explicit sign, e.g. "+0.42"; CLV is directional, so the sign carries meaning. */
export function signedPoints(value: number | null): string {
  if (value === null) return PENDING
  const fixed = value.toFixed(2)
  return value > 0 ? `+${fixed}` : fixed
}
