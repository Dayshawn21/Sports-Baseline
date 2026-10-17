import type { PropRankingRecord } from '~/types/propRanking'

export interface NbaModelSummary {
  slicesAdopted: string
  lastSettledWeek: string
  projectionVersion: string
  overProbabilityVersion: string
}

const PENDING = '—'

/** The `/nba/model` summary strip; every figure waits on the ranking check, the page's one section. */
export function nbaModelSummary(ranking: PropRankingRecord | undefined): NbaModelSummary {
  if (!ranking) {
    return { slicesAdopted: PENDING, lastSettledWeek: PENDING, projectionVersion: PENDING, overProbabilityVersion: PENDING }
  }
  const adopted = ranking.slices.filter((slice) => slice.verdict === 'adopt').length
  return {
    slicesAdopted: `${adopted} of ${ranking.slices.length}`,
    lastSettledWeek: ranking.lastSettledWeek === null ? 'None yet' : `W${ranking.lastSettledWeek}`,
    projectionVersion: ranking.modelVersion,
    overProbabilityVersion: ranking.overProbabilityVersion,
  }
}
