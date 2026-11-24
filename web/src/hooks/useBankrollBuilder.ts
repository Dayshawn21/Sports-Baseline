import { useQuery } from '@tanstack/react-query'
import { fetchBankrollBuilder } from '~/api/tennis'
import { SLATE_STALE_MS } from '~/hooks/queryTimes'

export function useBankrollBuilder(params?: { date?: string; tour?: string }) {
  return useQuery({
    queryKey: ['tennis', 'bankroll', params ?? 'default'],
    queryFn: () => fetchBankrollBuilder(params),
    staleTime: SLATE_STALE_MS,
    retry: 2,
  })
}
