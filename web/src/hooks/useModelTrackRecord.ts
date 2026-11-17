import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { fetchModelPredictions, fetchModelPrizePicksLines, fetchModelPropTiers } from '~/api/tennis'
import { TRACK_RECORD_STALE_MS } from '~/hooks/queryTimes'

/** No version means the served one; the previous version's data stays up while a switch loads. */
export function useModelPredictions(modelVersion?: string) {
  return useQuery({
    queryKey: ['tennis', 'model', 'predictions', { modelVersion }],
    queryFn: () => fetchModelPredictions(modelVersion),
    staleTime: TRACK_RECORD_STALE_MS,
    placeholderData: keepPreviousData,
  })
}

export function useModelPrizePicksLines() {
  return useQuery({
    queryKey: ['tennis', 'model', 'prizepicks-lines'],
    queryFn: fetchModelPrizePicksLines,
    staleTime: TRACK_RECORD_STALE_MS,
  })
}

export function useModelPropTiers() {
  return useQuery({
    queryKey: ['tennis', 'model', 'prop-tiers'],
    queryFn: fetchModelPropTiers,
    staleTime: TRACK_RECORD_STALE_MS,
  })
}
