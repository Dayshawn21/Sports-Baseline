import { useQuery } from '@tanstack/react-query'
import { fetchMatchRecentForm } from '~/api/tennis'
import { SLATE_STALE_MS } from '~/hooks/queryTimes'

export function useMatchRecentForm(matchId: number | null) {
  return useQuery({
    queryKey: ['tennis', 'match-recent-form', matchId],
    queryFn: () => fetchMatchRecentForm(matchId!),
    enabled: matchId != null,
    staleTime: SLATE_STALE_MS,
  })
}
