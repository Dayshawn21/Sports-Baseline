import { useQuery } from '@tanstack/react-query'
import { fetchPlayerDetail, fetchPlayerMatches, fetchPlayerProps, fetchPlayerServeReturn } from '~/api/tennis'
import { retryUnlessNotFound } from '~/utils/httpError'

const PLAYER_STALE_MS = 5 * 60 * 1000

export function usePlayerDetail(playerId: number | null) {
  return useQuery({
    queryKey: ['tennis', 'player', playerId, 'detail'],
    queryFn: () => fetchPlayerDetail(playerId!),
    enabled: playerId != null,
    staleTime: PLAYER_STALE_MS,
    retry: retryUnlessNotFound,
  })
}

export function usePlayerServeReturn(playerId: number | null) {
  return useQuery({
    queryKey: ['tennis', 'player', playerId, 'serve-return'],
    queryFn: () => fetchPlayerServeReturn(playerId!),
    enabled: playerId != null,
    staleTime: PLAYER_STALE_MS,
  })
}

export function usePlayerMatches(playerId: number | null) {
  return useQuery({
    queryKey: ['tennis', 'player', playerId, 'matches'],
    queryFn: () => fetchPlayerMatches(playerId!),
    enabled: playerId != null,
    staleTime: PLAYER_STALE_MS,
  })
}

export function usePlayerProps(playerId: number | null) {
  return useQuery({
    queryKey: ['tennis', 'player', playerId, 'props'],
    queryFn: () => fetchPlayerProps(playerId!),
    enabled: playerId != null,
    staleTime: PLAYER_STALE_MS,
  })
}
