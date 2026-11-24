import { useQuery } from '@tanstack/react-query'
import { fetchPrizePicksProps, fetchPrizePicksPropsAudit, fetchDKProps } from '~/api/tennis'

export function usePrizePicksProps() {
  return useQuery({
    queryKey: ['props', 'prizepicks'],
    queryFn: fetchPrizePicksProps,
    staleTime: 10 * 60 * 1000,
    retry: 2,
  })
}

export function usePrizePicksPropsAudit() {
  return useQuery({
    queryKey: ['props', 'prizepicks', 'audit'],
    queryFn: fetchPrizePicksPropsAudit,
    staleTime: 10 * 60 * 1000,
    retry: 2,
  })
}

/** `enabled` lets a page fetch a book's props only while it is the chosen source. */
export function useDKProps(enabled = true) {
  return useQuery({
    queryKey: ['props', 'dk'],
    queryFn: fetchDKProps,
    enabled,
    staleTime: 10 * 60 * 1000,
    retry: 2,
  })
}
