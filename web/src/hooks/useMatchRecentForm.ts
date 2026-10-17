import { useQuery } from '@tanstack/react-query'
import { fetchMatchRecentForm } from '~/api/tennis'

export function useMatchRecentForm(matchId: number | null) {
  return useQuery({
    queryKey: ['tennis', 'match-recent-form', matchId],
    queryFn: () => fetchMatchRecentForm(matchId!),
    enabled: matchId != null,
    staleTime: 5 * 60 * 1000,
  })
}
