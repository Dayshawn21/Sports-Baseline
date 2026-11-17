import { useQuery } from '@tanstack/react-query'
import { fetchMatchDetail } from '~/api/tennis'
import { retryUnlessNotFound } from '~/utils/httpError'
import { SLATE_STALE_MS } from '~/hooks/queryTimes'

export function useMatchDetail(matchId: number | null) {
  return useQuery({
    queryKey: ['tennis', 'match', matchId],
    queryFn: () => fetchMatchDetail(matchId!),
    enabled: matchId != null,
    staleTime: SLATE_STALE_MS,
    retry: retryUnlessNotFound,
  })
}
