import { useQuery } from '@tanstack/react-query'
import { fetchNflModelClv, fetchNflModelFit, fetchNflModelPropLines, fetchNflModelRanking } from '~/api/nfl'
import type { NflRankingModelVersion } from '~/types/nfl'
import { rankingQueryKey } from '~/utils/nflTrackRecord'

// The API caches each section for 15 minutes, so refetching sooner gains nothing.
const TRACK_RECORD_STALE_MS = 15 * 60 * 1000

export function useNflModelRanking(season: number | null, modelVersion?: NflRankingModelVersion) {
  return useQuery({
    queryKey: rankingQueryKey(season, modelVersion),
    queryFn: () => fetchNflModelRanking(season as number, modelVersion),
    enabled: season !== null,
    staleTime: TRACK_RECORD_STALE_MS,
  })
}

export function useNflModelPropLines(season: number | null) {
  return useQuery({
    queryKey: ['nfl', 'model', 'prop-lines', { season }],
    queryFn: () => fetchNflModelPropLines(season as number),
    enabled: season !== null,
    staleTime: TRACK_RECORD_STALE_MS,
  })
}

export function useNflModelClv(season: number | null) {
  return useQuery({
    queryKey: ['nfl', 'model', 'game-line-clv', { season }],
    queryFn: () => fetchNflModelClv(season as number),
    enabled: season !== null,
    staleTime: TRACK_RECORD_STALE_MS,
  })
}

export function useNflModelFit() {
  return useQuery({
    queryKey: ['nfl', 'model', 'over-probability-fit'],
    queryFn: fetchNflModelFit,
    staleTime: Infinity,
  })
}
