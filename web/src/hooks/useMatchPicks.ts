import { useQuery } from '@tanstack/react-query'
import { fetchBestPicks } from '~/api/tennis'
import type { MatchDetail } from '~/types/tennis'
import { canLoadMatchPicks } from '~/utils/tennisMatchBoard'
import { SLATE_STALE_MS } from '~/hooks/queryTimes'

export function useMatchPicks(detail: MatchDetail) {
  const date = detail.startUtc?.slice(0, 10)
  return useQuery({
    queryKey: ['tennis', 'match-picks', detail.matchId, date],
    queryFn: () => fetchBestPicks({ date }),
    enabled: canLoadMatchPicks(detail),
    staleTime: SLATE_STALE_MS,
    retry: 2,
  })
}
