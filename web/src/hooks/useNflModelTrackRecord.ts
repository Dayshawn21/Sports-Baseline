import { queryOptions, skipToken, useQuery } from '@tanstack/react-query'
import { fetchNflModelClv, fetchNflModelFit, fetchNflModelPropLines, fetchNflModelRanking } from '~/api/nfl'
import type { NflRankingModelVersion } from '~/types/nfl'
import { rankingQueryKey } from '~/utils/nflTrackRecord'
import { TRACK_RECORD_STALE_MS } from '~/hooks/queryTimes'

export function nflModelRankingQuery(season: number | null, modelVersion?: NflRankingModelVersion) {
  return queryOptions({
    queryKey: rankingQueryKey(season, modelVersion),
    queryFn: season === null ? skipToken : () => fetchNflModelRanking(season, modelVersion),
    staleTime: TRACK_RECORD_STALE_MS,
  })
}

export function nflModelPropLinesQuery(season: number | null) {
  return queryOptions({
    queryKey: ['nfl', 'model', 'prop-lines', { season }],
    queryFn: season === null ? skipToken : () => fetchNflModelPropLines(season),
    staleTime: TRACK_RECORD_STALE_MS,
  })
}

export function nflModelClvQuery(season: number | null) {
  return queryOptions({
    queryKey: ['nfl', 'model', 'game-line-clv', { season }],
    queryFn: season === null ? skipToken : () => fetchNflModelClv(season),
    staleTime: TRACK_RECORD_STALE_MS,
  })
}

export function useNflModelRanking(season: number | null, modelVersion?: NflRankingModelVersion) {
  return useQuery(nflModelRankingQuery(season, modelVersion))
}

export function useNflModelPropLines(season: number | null) {
  return useQuery(nflModelPropLinesQuery(season))
}

export function useNflModelClv(season: number | null) {
  return useQuery(nflModelClvQuery(season))
}

export function useNflModelFit() {
  return useQuery({
    queryKey: ['nfl', 'model', 'over-probability-fit'],
    queryFn: fetchNflModelFit,
    staleTime: Infinity,
  })
}
