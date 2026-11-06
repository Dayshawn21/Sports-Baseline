import { queryOptions, useQuery } from '@tanstack/react-query'
import { fetchPlayerDetail, fetchPlayerMatches, fetchPlayerProps, fetchPlayerServeReturn, fetchPlayerStats } from '~/api/tennis'
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

export function usePlayerMatches(playerId: number | null, limit?: number) {
  return useQuery({
    queryKey: ['tennis', 'player', playerId, 'matches', limit ?? 'default'],
    queryFn: () => fetchPlayerMatches(playerId!, limit),
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

/** Keyed on primitives so a match object rebuilt per render reuses the cached stats (F-27). */
export function playerStatsQuery(name: string, tour?: string | null, surface?: string | null) {
  const params = { name, tour: tour ?? null, surface: surface ?? null }
  return queryOptions({
    queryKey: ['tennis', 'player-stats', params],
    queryFn: () => fetchPlayerStats(params.name, params.tour, params.surface),
    staleTime: PLAYER_STALE_MS,
  })
}

export function usePlayerStats(name: string, tour?: string | null, surface?: string | null) {
  return useQuery(playerStatsQuery(name, tour, surface))
}
