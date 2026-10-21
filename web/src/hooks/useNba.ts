import { useQuery } from '@tanstack/react-query'
import { fetchNbaGame, fetchNbaLineOnlyProps, fetchNbaModelRanking, fetchNbaPropBoard, fetchNbaProps, fetchNbaSlate, fetchNbaSlateGaps } from '~/api/nba'
import type { PropRankingRecord } from '~/types/propRanking'
import { retryUnlessNotFound } from '~/utils/httpError'

export function useNbaSlate(date: string | null) {
  return useQuery({
    queryKey: ['nba', 'slate', date],
    queryFn: () => fetchNbaSlate(date),
    staleTime: 5 * 60 * 1000,
  })
}

export function useNbaPropBoard(date: string | null) {
  return useQuery({
    queryKey: ['nba', 'prop-board', date],
    queryFn: () => fetchNbaPropBoard(date),
    staleTime: 5 * 60 * 1000,
  })
}

/** The digest for a date the slate has already resolved; waits for it. */
export function useNbaSlateGaps(date: string | null) {
  return useQuery({
    queryKey: ['nba', 'slate', date, 'gaps'],
    queryFn: () => fetchNbaSlateGaps(date as string),
    enabled: date !== null,
    staleTime: 5 * 60 * 1000,
  })
}

export function useNbaGame(gameId: number | null) {
  return useQuery({
    queryKey: ['nba', 'game', gameId],
    queryFn: () => fetchNbaGame(gameId as number),
    enabled: gameId !== null,
    staleTime: 5 * 60 * 1000,
    retry: retryUnlessNotFound,
  })
}

export function useNbaLineOnlyProps(gameId: number | null) {
  return useQuery({
    queryKey: ['nba', 'game', gameId, 'line-only-props'],
    queryFn: () => fetchNbaLineOnlyProps(gameId as number),
    enabled: gameId !== null,
    staleTime: 5 * 60 * 1000,
    retry: retryUnlessNotFound,
  })
}

export function useNbaProps(gameId: number | null) {
  return useQuery({
    queryKey: ['nba', 'game', gameId, 'props'],
    queryFn: () => fetchNbaProps(gameId as number),
    enabled: gameId !== null,
    staleTime: 5 * 60 * 1000,
    retry: retryUnlessNotFound,
  })
}

export function useNbaModelRanking() {
  return useQuery<PropRankingRecord, Error>({
    queryKey: ['nba', 'model', 'ranking', { season: 'current' }],
    queryFn: fetchNbaModelRanking,
    // The API caches the check for 15 minutes, so refetching sooner gains nothing.
    staleTime: 15 * 60 * 1000,
    retry: retryUnlessNotFound,
  })
}
