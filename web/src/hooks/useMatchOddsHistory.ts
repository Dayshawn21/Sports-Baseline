import { useQuery } from '@tanstack/react-query'
import { fetchMatchOddsHistory } from '~/api/tennis'
import type { MatchOddsMarket } from '~/types/tennis'
import { retryUnlessNotFound } from '~/utils/httpError'

export function useMatchOddsHistory(matchId: number | null, market: MatchOddsMarket) {
  return useQuery({
    queryKey: ['tennis', 'match-odds', matchId, market],
    queryFn: () => fetchMatchOddsHistory(matchId!, market),
    enabled: matchId != null,
    staleTime: 5 * 60 * 1000,
    retry: retryUnlessNotFound,
  })
}
