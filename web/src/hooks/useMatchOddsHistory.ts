import { useQuery } from '@tanstack/react-query'
import { fetchMatchOddsHistory } from '~/api/tennis'
import type { MatchOddsMarket } from '~/types/tennis'
import { retryUnlessNotFound } from '~/utils/httpError'
import { SLATE_STALE_MS } from '~/hooks/queryTimes'

export function useMatchOddsHistory(matchId: number | null, market: MatchOddsMarket) {
  return useQuery({
    queryKey: ['tennis', 'match-odds', matchId, market],
    queryFn: () => fetchMatchOddsHistory(matchId!, market),
    enabled: matchId != null,
    staleTime: SLATE_STALE_MS,
    retry: retryUnlessNotFound,
  })
}
