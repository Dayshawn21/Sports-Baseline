import { useQuery } from '@tanstack/react-query'
import { fetchPrizePicksProps, fetchPrizePicksPropsAudit, fetchDKProps, fetchBetProps } from '~/api/tennis'

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

export function useDKProps() {
  return useQuery({
    queryKey: ['props', 'dk'],
    queryFn: fetchDKProps,
    staleTime: 10 * 60 * 1000,
    retry: 2,
  })
}

export function useBetProps() {
  return useQuery({
    queryKey: ['props', 'bet'],
    queryFn: fetchBetProps,
    staleTime: 10 * 60 * 1000,
    retry: 2,
  })
}

