import { useQuery } from '@tanstack/react-query'
import { fetchNflCurrentWeek, fetchNflGame, fetchNflGameContext, fetchNflGameNotes, fetchNflLineOnlyProps, fetchNflPlayer, fetchNflSlate, fetchNflWeekLineOnlyProps } from '~/api/nfl'
import { retryUnlessNotFound } from '~/utils/httpError'

export function useNflSlate(season: number | null, week: number | null) {
  return useQuery({
    queryKey: ['nfl', 'slate', season, week],
    queryFn: () => fetchNflSlate(season as number, week as number),
    enabled: season !== null && week !== null,
    staleTime: 5 * 60 * 1000,
  })
}

export function useNflGameNotes(season: number | null, week: number | null) {
  return useQuery({
    queryKey: ['nfl', 'game-notes', season, week],
    queryFn: () => fetchNflGameNotes(season as number, week as number),
    enabled: season !== null && week !== null,
    staleTime: 5 * 60 * 1000,
  })
}

export function useNflCurrentWeek() {
  return useQuery({
    queryKey: ['nfl', 'current-week'],
    queryFn: fetchNflCurrentWeek,
    staleTime: 60 * 60 * 1000,
  })
}

export function useNflPlayer(playerId: number | null) {
  return useQuery({
    queryKey: ['nfl', 'player', playerId],
    queryFn: () => fetchNflPlayer(playerId as number),
    enabled: playerId !== null,
    staleTime: 5 * 60 * 1000,
    retry: retryUnlessNotFound,
  })
}

export function useNflLineOnlyProps(gameId: number) {
  return useQuery({
    queryKey: ['nfl', 'game', gameId, 'line-only'],
    queryFn: () => fetchNflLineOnlyProps(gameId),
    staleTime: 5 * 60 * 1000,
    retry: retryUnlessNotFound,
  })
}

export function useNflWeekLineOnlyProps(season: number | null, week: number | null) {
  return useQuery({
    queryKey: ['nfl', 'line-only', season, week],
    queryFn: () => fetchNflWeekLineOnlyProps(season as number, week as number),
    enabled: season !== null && week !== null,
    staleTime: 5 * 60 * 1000,
  })
}

export function useNflGame(gameId: number | null) {
  return useQuery({
    queryKey: ['nfl', 'game', gameId],
    queryFn: () => fetchNflGame(gameId as number),
    enabled: gameId !== null,
    staleTime: 5 * 60 * 1000,
    retry: retryUnlessNotFound,
  })
}

export function useNflGameContext(gameId: number | null) {
  return useQuery({
    queryKey: ['nfl', 'game', gameId, 'context'],
    queryFn: () => fetchNflGameContext(gameId as number),
    enabled: gameId !== null && Number.isSafeInteger(gameId) && gameId > 0,
    staleTime: 5 * 60 * 1000,
    retry: false,
  })
}
