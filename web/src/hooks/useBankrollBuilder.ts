import { useQuery } from '@tanstack/react-query'
import { fetchBankrollBuilder } from '~/api/tennis'

export function useBankrollBuilder(params?: { date?: string; tour?: string }) {
  return useQuery({
    queryKey: ['tennis', 'bankroll', params ?? 'default'],
    queryFn: () => fetchBankrollBuilder(params),
    staleTime: 5 * 60 * 1000,
    retry: 2,
  })
}
