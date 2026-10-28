import { useQuery } from '@tanstack/react-query'
import { fetchAskStatus } from '~/api/ask'
import { retryUnlessNotFound } from '~/utils/httpError'

export function useAskStatus() {
  return useQuery({
    queryKey: ['ask', 'status'],
    queryFn: fetchAskStatus,
    staleTime: 5 * 60 * 1000,
    retry: retryUnlessNotFound,
  })
}
