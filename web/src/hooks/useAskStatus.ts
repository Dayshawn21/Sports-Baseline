import { useQuery } from '@tanstack/react-query'
import { fetchAskStatus } from '~/api/ask'
import { retryUnlessNotFound } from '~/utils/httpError'
import { SLATE_STALE_MS } from '~/hooks/queryTimes'

export function useAskStatus() {
  return useQuery({
    queryKey: ['ask', 'status'],
    queryFn: fetchAskStatus,
    staleTime: SLATE_STALE_MS,
    retry: retryUnlessNotFound,
  })
}
