import { useQuery } from '@tanstack/react-query'
import { fetchBestPicks } from '~/api/tennis'
import type { MatchDetail } from '~/types/tennis'
import { canLoadMatchPicks } from '~/utils/tennisMatchBoard'

export function useMatchPicks(detail: MatchDetail) {
  const date = detail.startUtc?.slice(0, 10)
  return useQuery({
    queryKey: ['tennis', 'match-picks', detail.matchId, date],
    queryFn: () => fetchBestPicks({ date }),
    enabled: canLoadMatchPicks(detail),
    staleTime: 5 * 60 * 1000,
    retry: 2,
  })
}
