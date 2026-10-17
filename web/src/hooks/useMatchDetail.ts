import { useQuery } from '@tanstack/react-query'
import { fetchMatchDetail } from '~/api/tennis'
import { retryUnlessNotFound } from '~/utils/httpError'

export function useMatchDetail(matchId: number | null) {
  return useQuery({
    queryKey: ['tennis', 'match', matchId],
    queryFn: () => fetchMatchDetail(matchId!),
    enabled: matchId != null,
    staleTime: 5 * 60 * 1000,
    retry: retryUnlessNotFound,
  })
}
